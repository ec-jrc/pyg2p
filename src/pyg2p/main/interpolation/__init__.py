import os
import logging
from functools import partial

import numpy as np
import numpy.ma as ma
from pyg2p import Loggable

from . import grib_interpolation_lib
from .latlong import LatLong
from .scipy_interpolation_lib import InverseDistance
from ..exceptions import ApplicationException, NO_INTERTABLE_CREATED
import pyg2p.util.files
import pyg2p.util.numeric


class Interpolator(Loggable):
    _LOADED_INTERTABLES = {}
    _prefix = 'I'
    scipy_modes_nnear = {'nearest': 1, 'invdist': 4}
    suffixes = {'grib_nearest': 'grib_nearest', 'grib_invdist': 'grib_invdist',
                'nearest': 'scipy_nearest', 'invdist': 'scipy_invdist'}
    _format_intertable = 'tbl{prognum}_{source_file}_{target_size}_{suffix}.npy'.format

    def __init__(self, exec_ctx, mv_input):
        super().__init__()
        self._mv_grib = mv_input
        self.interpolate_with_grib = exec_ctx.interpolate_with_grib
        self._mode = exec_ctx.get('interpolation.mode')
        self._source_filename = pyg2p.util.files.filename(exec_ctx.get('input.file'))
        self._suffix = self.suffixes[self._mode]
        self._logger = logging.getLogger()
        self._intertable_dirs = exec_ctx.get('interpolation.dirs')
        self._rotated_target_grid = exec_ctx.get('interpolation.rotated_target')
        self._target_coords = LatLong(exec_ctx.get('interpolation.latMap'), exec_ctx.get('interpolation.lonMap'))
        self.mv_out = self._target_coords.missing_value
        self.parallel = exec_ctx.get('interpolation.parallel')
        self.format_intertablename = partial(self._format_intertable,
                                             source_file=pyg2p.util.files.normalize_filename(self._source_filename),
                                             target_size=self._target_coords.lats.size,
                                             suffix=self._suffix)
        # values used for interpolation table computation
        self._aux_val = None
        self._aux_gid = None
        self._aux_2nd_res_gid = None
        self._aux_2nd_res_val = None

        self.create_if_missing = exec_ctx.get('interpolation.create')
        self.grib_methods = {'grib_nearest': self.grib_nearest, 'grib_invdist': self.grib_inverse_distance}
        self.intertables_config = exec_ctx.configuration.intertables  # IntertablesConfiguration object

    def interpolate(self, lats, longs, v, grid_id, geodetic_info, gid=-1, is_second_res=False):
        if self.interpolate_with_grib:
            out_v = self.interpolate_grib(v, gid, grid_id, is_second_res=is_second_res)
        else:
            # interpolating gridded data with scipy kdtree
            out_v = self.interpolate_scipy(lats, longs, v, grid_id, geodetic_info)
        return out_v

    def _intertable_filename(self, grid_id):
        intertable_id = '{}{}_{}{}'.format(self._prefix, grid_id.replace('$', '_'), self._target_coords.identifier, self._suffix)
        if intertable_id not in self.intertables_config.vars:
            # return a new intertable filename to create
            if not self.create_if_missing:
                raise ApplicationException.get_exc(NO_INTERTABLE_CREATED)
            self.intertables_config.check_write()
            filename = self.format_intertablename(prognum='')
            tbl_fullpath = os.path.normpath(os.path.join(self._intertable_dirs['user'], filename))
            i = 1
            while pyg2p.util.files.exists(tbl_fullpath):
                filename = self.format_intertablename(prognum='_{}'.format(i))
                tbl_fullpath = os.path.normpath(os.path.join(self._intertable_dirs['user'], filename))
                i += 1
            return intertable_id, tbl_fullpath

        filename = self.intertables_config.vars[intertable_id]['filename']

        # tbl_fullpath is taken from user path if defined, otherwise comes from global configuration
        tbl_fullpath = None if not self._intertable_dirs.get('user') else os.path.normpath(os.path.join(self._intertable_dirs['user'], filename))
        if not tbl_fullpath or not pyg2p.util.files.exists(tbl_fullpath):
            tbl_fullpath = os.path.normpath(os.path.join(self._intertable_dirs['global'], filename))
            if not pyg2p.util.files.exists(tbl_fullpath):
                # will create a new intertable but with same filename/id
                # as an existing configuration was already found but file is missing for some reasons
                if not self.create_if_missing:
                    raise ApplicationException.get_exc(NO_INTERTABLE_CREATED)
                self.intertables_config.check_write()
                tbl_fullpath = os.path.normpath(os.path.join(self._intertable_dirs['user'], filename))
                self._logger.warn('An entry in configuration was found for {} but intertable does not exist.'.format(filename))
        return intertable_id, tbl_fullpath

    def _read_intertable(self, tbl_fullpath):

        if tbl_fullpath not in self._LOADED_INTERTABLES:
            intertable = np.load(tbl_fullpath)
            self._LOADED_INTERTABLES[tbl_fullpath] = intertable
            self._log('Using interpolation table: {}'.format(tbl_fullpath), 'INFO')
        else:
            intertable = self._LOADED_INTERTABLES[tbl_fullpath]

        if self._mode == 'grib_nearest':
            # grib nearest neighbour table
            return intertable[0], intertable[1], intertable[2]
        elif self._mode == 'grib_invdist':
            # grib inverse distance table is a recorded numpy array with keys 'indexes' and 'coeffs'
            indexes = intertable['indexes']  # first two arrays of this group are target xs and ys indexes
            coeffs = intertable['coeffs']
            return indexes[0], indexes[1], indexes[2], indexes[3], indexes[4], indexes[5], coeffs[0], coeffs[1], coeffs[2], coeffs[3]
        else:
            # self._mode in ('invdist', 'nearest'):
            # return indexes and weighted distances (only used with nnear=4)
            indexes = intertable['indexes']
            coeffs = intertable['coeffs']
            return indexes, coeffs

    # ####### SCIPY INTERPOLATION ###################################
    def _interpolate_scipy_invdist(self, v, weights, indexes, nnear):
        # append the MV efas value at the end because of how KDTree algo works
        # It gives (last_index + 1) from original values when value can't be computed.
        # These "last_index + 1" indexes are stored in intertable so we artificially add a missing value
        # v[last_index + 1] = mv
        v = np.append(v, self.mv_output)
        orig_mask = False if not isinstance(v, ma.core.MaskedArray) else v.mask
        if nnear == 1:
            if isinstance(orig_mask, np.ndarray):
                result = ma.masked_where(orig_mask[indexes], v[indexes], copy=False)
            else:
                result = v[indexes]
        else:
            result = np.einsum('ij,ij->i', weights, v[indexes])
            if isinstance(orig_mask, np.ndarray):
                # there are masks. logic sum of masks from all values used
                mask = None
                for i in range(0, indexes.shape[1]):
                    mask = orig_mask[indexes.T[i]] if mask is None else mask | orig_mask[indexes.T[i]]
                result = ma.masked_where(mask, result, copy=False)
        return result

    def interpolate_scipy(self, latgrib, longrib, v, grid_id, grid_details=None):

        intertable_id, intertable_name = self._intertable_filename(grid_id)
        lonefas = self._target_coords.longs
        latefas = self._target_coords.lats

        nnear = self.scipy_modes_nnear[self._mode]

        if pyg2p.util.files.exists(intertable_name):
            indexes, weights = self._read_intertable(intertable_name)
            result = self._interpolate_scipy_invdist(v, weights, indexes, nnear)

        elif self.create_if_missing:
            self.intertables_config.check_write()
            if latgrib is None:
                self._log('Trying to interpolate without grib lat/lons. Probably a malformed grib!', 'ERROR')
                raise ApplicationException.get_exc(5000)

            self._log('\nInterpolating table not found\n Id: {}\nWill create file: {}'.format(intertable_id, intertable_name), 'WARN')
            invdisttree = InverseDistance(longrib, latgrib, grid_details, v.ravel(), nnear, self.mv_out,
                                          self._mv_grib, target_is_rotated=self._rotated_target_grid,
                                          parallel=self.parallel)
            _, weights, indexes = invdisttree.interpolate(lonefas, latefas)
            result = self._interpolate_scipy_invdist(v, weights, indexes, nnear)

            # saving interpolation lookup table
            intertable = np.rec.fromarrays((indexes, weights), names=('indexes', 'coeffs'))
            np.save(intertable_name, intertable)
            self.update_intertable_conf(intertable, intertable_id, intertable_name, v.shape)
        else:
            raise ApplicationException.get_exc(NO_INTERTABLE_CREATED, details=intertable_name)

        # reshape to target (e.g. efas, glofas...)
        grid_data = result.reshape(lonefas.shape)
        return grid_data

    # #### GRIB API INTERPOLATION ####################
    def interpolate_grib(self, v, gid, grid_id, is_second_res=False):
        return self.grib_methods[self._mode](v, gid, grid_id, is_second_res=is_second_res)

    def grib_nearest(self, v, gid, grid_id, is_second_res=False, intertable_id=None, intertable_name=None):
        if not intertable_name:
            intertable_id, intertable_name = self._intertable_filename(grid_id)
        result = np.empty(self._target_coords.longs.shape)
        result.fill(self.mv_out)
        if gid == -1 and not pyg2p.util.files.exists(intertable_name):
            # calling recursive grib_nearest
            # aux_gid and aux_values are only used to create the interlookuptable
            if is_second_res:
                self.grib_nearest(self._aux_2nd_res_val, self._aux_2nd_res_gid, grid_id,
                                  intertable_name=intertable_name, intertable_id=intertable_id,
                                  is_second_res=is_second_res)
            else:
                self.grib_nearest(self._aux_val, self._aux_gid, grid_id,
                                  intertable_name=intertable_name, intertable_id=intertable_id)

        if pyg2p.util.files.exists(intertable_name):
            # interpolation using intertables
            xs, ys, idxs = self._read_intertable(intertable_name)

        elif self.create_if_missing:
            try:
                assert gid != -1, 'GRIB message reference was not found.'
            except AssertionError as e:
                raise ApplicationException.get_exc(6000, details=str(e))
            self.intertables_config.check_write()
            self._log('\nInterpolating table not found\n Id: {}\nWill create file: {}'.format(intertable_id, intertable_name), 'WARN')
            xs, ys, idxs = getattr(grib_interpolation_lib, 'grib_nearest{}'.format('' if not self.parallel else '_parallel'))(gid, self._target_coords.lats, self._target_coords.longs, self._target_coords.missing_value)
            intertable = np.asarray([xs, ys, idxs])
            np.save(intertable_name, intertable)
            self.update_intertable_conf(intertable, intertable_id, intertable_name, v.shape)
        else:
            if intertable_id not in self.intertables_config.vars:
                d = {'filename': pyg2p.util.files.filename(intertable_name),
                     'method': self._mode,
                     'source_shape': v.shape,
                     'target_shape': self._target_coords.longs.shape}
                self._log('If you already have an intertable file, add this configuration to intertables.json and change filename. {} {}'.format(intertable_id, d), 'INFO')
            raise ApplicationException.get_exc(NO_INTERTABLE_CREATED, details=intertable_name)
        result[xs, ys] = pyg2p.util.numeric.result_masked(v[idxs], self.mv_output)
        return result

    def grib_inverse_distance(self, v, gid, grid_id, is_second_res=False, intertable_id=None, intertable_name=None):
        if not intertable_name:
            intertable_id, intertable_name = self._intertable_filename(grid_id)

        result = np.empty(self._target_coords.longs.shape)
        result.fill(self.mv_out)

        # check if gid is due to the recursive call
        if gid == -1 and not pyg2p.util.files.exists(intertable_name):
            # aux_gid and aux_values are only used to create the interlookuptable
            # since manipulated values messages don't have gid reference to grib file any longer
            aux_gid = self._aux_gid
            aux_val = self._aux_val
            if is_second_res:
                aux_gid = self._aux_2nd_res_gid
                aux_val = self._aux_2nd_res_val
            self.grib_inverse_distance(aux_val, aux_gid, grid_id, intertable_name=intertable_name,
                                       intertable_id=intertable_id, is_second_res=is_second_res)

        if pyg2p.util.files.exists(intertable_name):
            # interpolation using intertables
            xs, ys, idxs1, idxs2, idxs3, idxs4, coeffs1, coeffs2, coeffs3, coeffs4 = self._read_intertable(intertable_name)
        elif self.create_if_missing:
            # assert...
            if gid == -1:
                raise ApplicationException.get_exc(6000)

            self._log('\nInterpolating table not found. Will create file: {}'.format(intertable_name), 'WARN')
            lonefas = self._target_coords.longs
            latefas = self._target_coords.lats
            mv = self._target_coords.missing_value
            intrp_result = getattr(grib_interpolation_lib, 'grib_invdist{}'.format('' if not self.parallel else '_parallel'))(gid, latefas, lonefas, mv)
            xs, ys, idxs1, idxs2, idxs3, idxs4, coeffs1, coeffs2, coeffs3, coeffs4 = intrp_result
            indexes = np.asarray([xs, ys, idxs1, idxs2, idxs3, idxs4])
            coeffs = np.asarray([coeffs1, coeffs2, coeffs3, coeffs4, np.zeros(coeffs1.shape), np.zeros(coeffs1.shape)])
            intertable = np.rec.fromarrays((indexes, coeffs), names=('indexes', 'coeffs'))
            # saving interpolation lookup table
            np.save(intertable_name, intertable)
            self.update_intertable_conf(intertable, intertable_id, intertable_name, v.shape)

        else:
            if intertable_id not in self.intertables_config.vars:
                d = {'filename': pyg2p.util.files.filename(intertable_name),
                     'method': self._mode,
                     'source_shape': v.shape,
                     'target_shape': self._target_coords.longs.shape}
                self._log('If you already have an intertable file, add this configuration to intertables.json and change filename. {} {}'.format(intertable_id, d), 'INFO')
            raise ApplicationException.get_exc(NO_INTERTABLE_CREATED, details=intertable_name)

        res = v[idxs1] * coeffs1 + v[idxs2] * coeffs2 + v[idxs3] * coeffs3 + v[idxs4] * coeffs4
        result[xs, ys] = pyg2p.util.numeric.result_masked(res, self.mv_output)
        return result

    def update_intertable_conf(self, intertable, intertable_id, intertable_name, source_shape):
        self._LOADED_INTERTABLES[intertable_name] = intertable
        new_intertable_conf_item = {'filename': pyg2p.util.files.filename(intertable_name),
                                    'method': self._mode,
                                    'source_shape': source_shape,
                                    'target_shape': self._target_coords.longs.shape}
        # update global configuration
        self.intertables_config.vars[intertable_id] = new_intertable_conf_item

        # Dumps only user configuration to ~/.pyg2p/intertables.json
        self.intertables_config.user_vars[intertable_id] = new_intertable_conf_item
        self.intertables_config.dump()

    # set aux gids for grib interlookup creation
    def aux_for_intertable_generation(self, aux_g, aux_v, aux_g2, aux_v2):
        self._aux_gid = aux_g
        self._aux_val = aux_v
        self._aux_2nd_res_gid = aux_g2
        self._aux_2nd_res_val = aux_v2

    @property
    def mv_output(self):
        return self.mv_out
