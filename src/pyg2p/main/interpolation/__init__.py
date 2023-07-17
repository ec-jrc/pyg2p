import gzip
import os
import logging
from functools import partial

import numpy as np
import numpy.ma as ma
from pyg2p import Loggable

from . import grib_interpolation_lib
from .latlong import LatLong
from .scipy_interpolation_lib import ScipyInterpolation, DEBUG_BILINEAR_INTERPOLATION, DEBUG_ADW_INTERPOLATION, \
                                        DEBUG_MIN_LAT, DEBUG_MIN_LON, DEBUG_MAX_LAT, DEBUG_MAX_LON
                                        
from ...exceptions import ApplicationException, NO_INTERTABLE_CREATED
import pyg2p.util.files
import pyg2p.util.numeric


class Interpolator(Loggable):
    _LOADED_INTERTABLES = {}
    _prefix = 'I'
    scipy_modes_nnear = {'nearest': 1, 'invdist': 4, 'adw': 4, 'cdd': 4, 'bilinear': 4, 'triangulation': 3, 'bilinear_delaunay': 4}
    suffixes = {'grib_nearest': 'grib_nearest', 'grib_invdist': 'grib_invdist',
                'nearest': 'scipy_nearest', 'invdist': 'scipy_invdist', 'adw': 'scipy_adw', 'cdd': 'scipy_cdd',
                'bilinear': 'scipy_bilinear', 'triangulation': 'scipy_triangulation', 'bilinear_delaunay': 'scipy_bilinear_delaunay'}
    _format_intertable = 'tbl{prognum}_{source_file}_{target_size}_{suffix}.npy.gz'.format

    def __init__(self, exec_ctx, mv_input):
        super().__init__()
        self._mv_grib = mv_input
        self.interpolate_with_grib = exec_ctx.is_with_grib_interpolation
        self._mode = exec_ctx.get('interpolation.mode')
        self._adw_broadcasting = exec_ctx.get('interpolation.adw_broadcasting')
        self._source_filename = pyg2p.util.files.filename(exec_ctx.get('input.file'))
        self._suffix = self.suffixes[self._mode]
        self._intertable_dirs = exec_ctx.get('interpolation.dirs')
        self._rotated_target_grid = exec_ctx.get('interpolation.rotated_target')
        self._target_coords = LatLong(exec_ctx.get('interpolation.latMap'), exec_ctx.get('interpolation.lonMap'))
        self.mv_out = self._target_coords.mv
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
                raise ApplicationException.get_exc(NO_INTERTABLE_CREATED, details=f'Using {intertable_id}')
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
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug(f'Using {tbl_fullpath} for id {intertable_id}')
        if not tbl_fullpath or not (pyg2p.util.files.exists(tbl_fullpath) or pyg2p.util.files.exists(tbl_fullpath + '.gz')):
            tbl_fullpath = os.path.normpath(os.path.join(self._intertable_dirs['global'], filename))
            if not (pyg2p.util.files.exists(tbl_fullpath) or pyg2p.util.files.exists(tbl_fullpath + '.gz')):
                # will create a new intertable but with same filename/id
                # as an existing configuration was already found but file is missing for some reasons
                if not self.create_if_missing:
                    raise ApplicationException.get_exc(NO_INTERTABLE_CREATED, details=f'Tried to create {tbl_fullpath}')
                self.intertables_config.check_write()
                tbl_fullpath = os.path.normpath(os.path.join(self._intertable_dirs['user'], filename))
                tbl_fullpath = tbl_fullpath if tbl_fullpath.endswith('.gz') else tbl_fullpath + '.gz'
                self._logger.warning(f'An entry in configuration was found for {filename} but intertable does not exist.')
        return intertable_id, tbl_fullpath

    def _read_intertable(self, tbl_fullpath):

        if tbl_fullpath not in self._LOADED_INTERTABLES:
            f = tbl_fullpath
            if tbl_fullpath.endswith('.gz'):
                f = gzip.GzipFile(tbl_fullpath, 'r')
                intertable = np.load(f)
                f.close()
            else:
                try:
                    intertable = np.load(tbl_fullpath)
                except FileNotFoundError:
                    f = tbl_fullpath + '.gz'
                    if not pyg2p.util.files.exists(f):
                        raise ApplicationException.get_exc(NO_INTERTABLE_CREATED, details=f'Tried to read both {tbl_fullpath} and {f} but none was found')
                    f = gzip.GzipFile(f, 'r')
                    intertable = np.load(f)
                    f.close()
            self._LOADED_INTERTABLES[tbl_fullpath] = intertable
            self._log(f'Using interpolation table: {tbl_fullpath}', 'INFO')
        else:
            intertable = self._LOADED_INTERTABLES[tbl_fullpath]

        if self._mode == 'grib_nearest':
            # grib nearest neighbour table
            return intertable[0], intertable[1], intertable[2]
        elif self._mode == 'grib_invdist':
            # grib inverse distance table is a "recorded numpy array" with keys 'indexes' and 'coeffs'
            indexes = intertable['indexes']  # first two arrays of this group are target xs and ys indexes
            coeffs = intertable['coeffs']
            return indexes[0], indexes[1], indexes[2], indexes[3], indexes[4], indexes[5], coeffs[0], coeffs[1], coeffs[2], coeffs[3]
        else:
            # self._mode in ('invdist', 'adw', 'cdd', 'nearest', 'bilinear', 'triangulation', 'bilinear_delaunay'):
            # return indexes and weighted distances (only used with nnear > 1)
            indexes = intertable['indexes']
            coeffs = intertable['coeffs']
            return indexes, coeffs

    # ####### SCIPY INTERPOLATION ###################################
    def _interpolate_scipy_append_mv(self, v, weights, indexes, nnear):
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
        lonefas = self._target_coords.lons
        latefas = self._target_coords.lats
        if DEBUG_BILINEAR_INTERPOLATION:
            # target_lats=target_lats[1800-(9*20):1800-(-16*20), 3600+(-15*20):3600+(16*20)]
            # target_lons=target_lons[1800-(9*20):1800-(-16*20), 3600+(-15*20):3600+(16*20)]
            if self._target_coords.lats.shape==(3600,7200):
                # Global_3arcmin DEBUG
                latefas=self._target_coords.lats[1800-int(DEBUG_MAX_LAT*20):1800-int(DEBUG_MIN_LAT*20), 3600+int(DEBUG_MIN_LON*20):3600+int(DEBUG_MAX_LON*20)]
                lonefas=self._target_coords.lons[1800-int(DEBUG_MAX_LAT*20):1800-int(DEBUG_MIN_LAT*20), 3600+int(DEBUG_MIN_LON*20):3600+int(DEBUG_MAX_LON*20)]
            else:
                # European_1arcmin DEBUG
                selection_lats = np.logical_and(self._target_coords.lats[:,0]>=DEBUG_MIN_LAT,self._target_coords.lats[:,0]<=DEBUG_MAX_LAT)
                selection_lons = np.logical_and(self._target_coords.lons[0,:]>=DEBUG_MIN_LON,self._target_coords.lons[0,:]<=DEBUG_MAX_LON)
                latefas=self._target_coords.lats[selection_lats,:][:,selection_lons]
                lonefas=self._target_coords.lons[selection_lats,:][:,selection_lons]

            intertable_id, intertable_name = 'DEBUG','DEBUG.npy'
        else:
            intertable_id, intertable_name = self._intertable_filename(grid_id)

        if DEBUG_ADW_INTERPOLATION:
            # to debug create a limited controlled set of input values 
            #
            # np.random.seed(0)
            # latgrib = np.random.uniform(low=3, high=11, size=10)
            # longrib = np.random.uniform(low=46, high=50, size=10)
            # v = np.random.uniform(low=100, high=200, size=10)
            # latgrib = np.array([ 7.39050803,  8.72151493,  7.82210701,  7.35906546,  6.38923839,
            #     8.1671529,  6.50069769, 10.13418401, 10.70930208,  6.06753215])
            # longrib = np.array([49.16690015, 48.11557968, 48.27217824, 49.70238655, 46.28414423,
            #     46.3485172, 46.08087359, 49.33047938, 49.112627, 49.48004859])
            # v = np.array([197.86183422, 179.91585642, 146.14793623, 178.05291763, 111.82744259, 
            #     163.99210213, 114.33532874, 194.4668917, 152.18483218, 141.466194  ])
            # latgrib = np.array([ 7.39050803,  8.72151493,  7.82210701,  7.35906546])
            # longrib = np.array([49.16690015, 48.11557968, 48.27217824, 49.70238655])
            # v = np.array([100, 133, 166, 200  ])
            latgrib = np.array([ 8,  8,  8,  8])
            longrib = np.array([45, 48.5, 49, 50])
            v = np.array([200, 100, 100, 100  ])
            intertable_id, intertable_name = 'DEBUG_ADW','DEBUG_ADW.npy'

        nnear = self.scipy_modes_nnear[self._mode]

        if (not DEBUG_ADW_INTERPOLATION) and \
            (pyg2p.util.files.exists(intertable_name) or pyg2p.util.files.exists(intertable_name + '.gz')):
                indexes, weights = self._read_intertable(intertable_name)
                result = self._interpolate_scipy_append_mv(v, weights, indexes, nnear)

        elif self.create_if_missing:
            self.intertables_config.check_write()
            if latgrib is None:
                self._log('Trying to interpolate without grib lat/lons. Probably a malformed grib!', 'ERROR')
                raise ApplicationException.get_exc(5000)

            self._log('\nInterpolating table not found\n Id: {}\nWill create file: {}'.format(intertable_id, intertable_name), 'WARN')
            scipy_interpolation = ScipyInterpolation(longrib, latgrib, grid_details, v.ravel(), nnear, self.mv_out,
                                          self._mv_grib, target_is_rotated=self._rotated_target_grid,
                                          parallel=self.parallel, mode=self._mode, use_broadcasting=self._adw_broadcasting)
            _, weights, indexes = scipy_interpolation.interpolate(lonefas, latefas)
            result = self._interpolate_scipy_append_mv(v, weights, indexes, nnear)

            # saving interpolation lookup table
            intertable = np.rec.fromarrays((indexes, weights), names=('indexes', 'coeffs'))
            if intertable_name.endswith('.gz'):
                f = gzip.GzipFile(intertable_name, 'w')
                np.save(f, intertable)
                f.close()
            else:
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
        result = np.empty(self._target_coords.lons.shape)
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
            if gid == -1:
                raise ApplicationException.get_exc(6000, details='GRIB message reference was not found.')
            self.intertables_config.check_write()
            self._log('\nInterpolating table not found\n Id: {}\nWill create file: {}'.format(intertable_id, intertable_name), 'WARN')
            xs, ys, idxs = getattr(grib_interpolation_lib, 'grib_nearest{}'.format('' if not self.parallel else '_parallel'))(gid, self._target_coords.lats, self._target_coords.lons, self._target_coords.mv)
            intertable = np.asarray([xs, ys, idxs])
            if intertable_name.endswith('.gz'):
                f = gzip.GzipFile(intertable_name, 'w')
                np.save(f, intertable)
                f.close()
            else:
                np.save(intertable_name, intertable)
            self.update_intertable_conf(intertable, intertable_id, intertable_name, v.shape)
        else:
            if intertable_id not in self.intertables_config.vars:
                d = {'filename': pyg2p.util.files.filename(intertable_name),
                     'method': self._mode,
                     'source_shape': v.shape,
                     'target_shape': self._target_coords.lons.shape}
                self._log('If you already have an intertable file, add this configuration to intertables.json and change filename. {} {}'.format(intertable_id, d), 'INFO')
            raise ApplicationException.get_exc(NO_INTERTABLE_CREATED, details=intertable_name)
        result[xs, ys] = pyg2p.util.numeric.result_masked(v[idxs], self.mv_output)
        return result

    def grib_inverse_distance(self, v, gid, grid_id, is_second_res=False, intertable_id=None, intertable_name=None):
        if not intertable_name:
            intertable_id, intertable_name = self._intertable_filename(grid_id)

        result = np.empty(self._target_coords.lons.shape)
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
            lonefas = self._target_coords.lons
            latefas = self._target_coords.lats
            mv = self._target_coords.mv
            intrp_result = getattr(grib_interpolation_lib, 'grib_invdist{}'.format('' if not self.parallel else '_parallel'))(gid, latefas, lonefas, mv)
            xs, ys, idxs1, idxs2, idxs3, idxs4, coeffs1, coeffs2, coeffs3, coeffs4 = intrp_result
            indexes = np.asarray([xs, ys, idxs1, idxs2, idxs3, idxs4])
            coeffs = np.asarray([coeffs1, coeffs2, coeffs3, coeffs4, np.zeros(coeffs1.shape), np.zeros(coeffs1.shape)])
            intertable = np.rec.fromarrays((indexes, coeffs), names=('indexes', 'coeffs'))
            # saving interpolation lookup table
            if intertable_name.endswith('.gz'):
                f = gzip.GzipFile(intertable_name, 'w')
                np.save(f, intertable)
                f.close()
            else:
                np.save(intertable_name, intertable)
            self.update_intertable_conf(intertable, intertable_id, intertable_name, v.shape)

        else:
            if intertable_id not in self.intertables_config.vars:
                d = {'filename': pyg2p.util.files.filename(intertable_name),
                     'method': self._mode,
                     'source_shape': v.shape,
                     'target_shape': self._target_coords.lons.shape}
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
                                    'target_shape': self._target_coords.lons.shape}
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
