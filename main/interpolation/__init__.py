import os
from functools import partial

import numpy as np

import util.files
from main.exceptions import ApplicationException, NO_INTERTABLE_CREATED
from main.interpolation import scipy_interpolation_lib as ID
from main.interpolation import grib_interpolation_lib
from main.interpolation.latlong import LatLong
from main.interpolation.scipy_interpolation_lib import InverseDistance
from util.logger import Logger
from util.numeric import mask_it


class Interpolator(object):
    _LOADED_INTERTABLES = {}
    _suffix_scipy = '_scipy_'
    _prefix = 'I'
    scipy_modes_nnear = {'nearest': 1, 'invdist': 4}
    suffixes = {'grib_nearest': '_nn', 'grib_invdist': '_inv',
                'nearest': '_scipy_nearest', 'invdist': '_scipy_invdist'}
    _format_intertable = 'tbl{prognum}_{source_file}_{target_size}_{mode}.npy'.format

    def __init__(self, exec_ctx):
        self._mode = exec_ctx.get('interpolation.mode')
        self._source_filename = util.files.filename(exec_ctx.get('input.file'))
        self._suffix = self.suffixes[self._mode]
        self._logger = Logger.get_logger()
        self._intertable_dir = exec_ctx.get('interpolation.dir')
        self._target_coords = LatLong(exec_ctx.get('interpolation.latMap'), exec_ctx.get('interpolation.lonMap'))
        self._mv_efas = self._target_coords.missing_value
        self._mv_grib = -1
        self.parallel = exec_ctx.get('interpolation.parallel')
        self.format_intertablename = partial(self._format_intertable, source_file=util.files.normalize_filename(self._source_filename),
                                             target_size=self._target_coords.lats.size,
                                             mode=self._mode)

        # values used for interpolation table computation
        self._aux_val = None
        self._aux_gid = None
        self._aux_2nd_res_gid = None
        self._aux_2nd_res_val = None

        self.create_if_missing = exec_ctx.get('interpolation.create')
        self.grib_methods = {'grib_nearest': self.grib_nearest, 'grib_invdist': self.grib_inverse_distance}
        self.intertables_config = exec_ctx.configuration.intertables
        self.intertables_dict = self.intertables_config.vars

    def _intertable_filename(self, grid_id):
        intertable_id = '{}{}_{}{}'.format(self._prefix, grid_id.replace('$', '_'), self._target_coords.identifier, self._suffix)
        if intertable_id not in self.intertables_dict:
            # return a new intertable filename
            filename = self.format_intertablename(prognum='')
            tbl_fullpath = os.path.normpath(os.path.join(self._intertable_dir, filename))
            i = 1
            while util.files.exists(tbl_fullpath):
                filename = self.format_intertablename(prognum='_{}'.format(i))
                tbl_fullpath = os.path.normpath(os.path.join(self._intertable_dir, filename))
                i += 1
            return intertable_id, tbl_fullpath

        filename = self.intertables_dict[intertable_id]['filename']
        tbl_fullpath = os.path.normpath(os.path.join(self._intertable_dir, filename))
        if not util.files.exists(tbl_fullpath):
            self._logger.warn('An entry in configuration was found for {} but intertable does not exist and will be created'.format(filename))
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

    @staticmethod
    def _interpolate_scipy_invdist(z, _mv_grib, weights, indexes, nnear):

        # TODO CHECK: maybe we don't need to mask here
        z = mask_it(z, _mv_grib)
        if nnear == 1:
            # for nnear = 1 it doesn't care at this point if indexes come from intertable
            # or were just queried from the tree
            result = z[indexes]
        else:
            result = np.einsum('ij,ij->i', weights, z[indexes])
        return result

    def interpolate_scipy(self, latgrib, longrib, z, grid_id, grid_details=None):
        intertable_id, intertable_name = self._intertable_filename(grid_id)
        lonefas = self._target_coords.longs
        latefas = self._target_coords.lats

        nnear = self.scipy_modes_nnear[self._mode]

        if util.files.exists(intertable_name):
            indexes, weights = self._read_intertable(intertable_name)
            result = self._interpolate_scipy_invdist(z, self._mv_grib, weights, indexes, nnear)
        elif self.create_if_missing:
            if latgrib is None:
                self._log('Trying to interpolate without grib lat/lons. Probably a geopotential grib!', 'ERROR')
                raise ApplicationException.get_programmatic_exc(5000)

            self._log('\nInterpolating table not found. Will create file: {}'.format(intertable_name), 'INFO')
            invdisttree = InverseDistance(longrib, latgrib, grid_details, z.ravel(), self._mv_efas, self._mv_grib)
            result, weights, indexes = invdisttree.interpolate(lonefas, latefas, nnear, parallel=self.parallel)
            # saving interpolation lookup table
            intertable = np.rec.fromarrays((indexes, weights), names=('indexes', 'coeffs'))
            np.save(intertable_name, intertable)
            self.update_intertable_conf(intertable, intertable_id, intertable_name, z.shape)
            # reshape to target (e.g. efas, glofas...)
        else:
            raise ApplicationException.get_programmatic_exc(NO_INTERTABLE_CREATED, details=intertable_name)

        grid_data = result.reshape(lonefas.shape)
        return grid_data

    # #### GRIB API INTERPOLATION ####################
    def interpolate_grib(self, v, gid, grid_id, second_spatial_resolution=False):
        return self.grib_methods[self._mode](v, gid, grid_id, second_spatial_resolution=second_spatial_resolution)

    def grib_nearest(self, v, gid, grid_id, second_spatial_resolution=False):
        intertable_id, intertable_name = self._intertable_filename(grid_id)
        existing_intertable = False

        # TODO CHECK these double call of masked values/fill
        result = np.empty(self._target_coords.longs.shape)
        result.fill(self._mv_efas)
        result = mask_it(result, self._mv_efas)

        if gid == -1 and not util.files.exists(intertable_name):
            # aux_gid and aux_values are only used to create the interlookuptable
            if second_spatial_resolution:
                self.grib_nearest(self._aux_2nd_res_val, self._aux_2nd_res_gid, grid_id, second_spatial_resolution=second_spatial_resolution)
            else:
                self.grib_nearest(self._aux_val, self._aux_gid, grid_id)

        if util.files.exists(intertable_name):
            # interpolation using intertables
            existing_intertable = True
            xs, ys, idxs = self._read_intertable(intertable_name)

            # TODO CHECK: maybe we don't need to mask here
            v = mask_it(v, self._mv_grib)

        elif self.create_if_missing:
            try:
                assert gid != -1, 'GRIB message reference was not found.'
            except AssertionError as e:
                raise ApplicationException.get_programmatic_exc(6000, details=str(e))
            self._log('\nInterpolating table not found. Will create file: {}'.format(intertable_name), 'INFO')
            xs, ys, idxs = getattr(grib_interpolation_lib, 'grib_nearest{}'.format('' if not self.parallel else '_parallel'))(gid, self._target_coords.lats, self._target_coords.longs, self._target_coords.missing_value)
            intertable = np.asarray([xs, ys, idxs])
            np.save(intertable_name, intertable)
            self.update_intertable_conf(intertable, intertable_id, intertable_name, v.shape)
        else:
            raise ApplicationException.get_programmatic_exc(NO_INTERTABLE_CREATED, details=intertable_name)

        result[xs, ys] = v[idxs]
        return result, existing_intertable

    def grib_inverse_distance(self, v, gid, grid_id, second_spatial_resolution=False):
        intertable_id, intertable_name = self._intertable_filename(grid_id)

        # TODO CHECK these double call of masked values
        result = np.empty(self._target_coords.longs.shape)
        result.fill(self._mv_efas)
        result = np.ma.masked_array(data=result, fill_value=self._mv_efas, copy=False)

        # TODO CHECK: maybe we don't need to mask here
        v = mask_it(v, self._mv_grib)

        existing_intertable = False
        # check if gid is due to the recursive call
        if gid == -1 and not util.files.exists(intertable_name):
            # aux_gid and aux_values are only used to create the interlookuptable
            # since manipulated values messages don't have gid reference to grib file any longer
            if second_spatial_resolution:
                self.grib_inverse_distance(self._aux_2nd_res_val, self._aux_2nd_res_gid, grid_id, second_spatial_resolution=second_spatial_resolution)
            else:
                self.grib_inverse_distance(self._aux_val, self._aux_gid, grid_id)

        if util.files.exists(intertable_name):
            # interpolation using intertables
            existing_intertable = True
            xs, ys, idxs1, idxs2, idxs3, idxs4, coeffs1, coeffs2, coeffs3, coeffs4 = self._read_intertable(intertable_name)
        elif self.create_if_missing:
            # assert...
            if gid == -1:
                raise ApplicationException.get_programmatic_exc(6000)
            self._log('\nInterpolating table not found. Will create file: {}'.format(intertable_name), 'INFO')
            lonefas = self._target_coords.longs
            latefas = self._target_coords.lats
            mv = self._target_coords.missing_value
            xs, ys, idxs1, idxs2, idxs3, idxs4, coeffs1, coeffs2, coeffs3, coeffs4 = getattr(grib_interpolation_lib, 'grib_invdist{}'.format('' if not self.parallel else '_parallel'))(gid, latefas, lonefas, mv)

            indexes = np.asarray([xs, ys, idxs1, idxs2, idxs3, idxs4])
            coeffs = np.asarray([coeffs1, coeffs2, coeffs3, coeffs4, np.zeros(coeffs1.shape), np.zeros(coeffs1.shape)])
            # intertable = np.asarray([xs, ys, idxs1, idxs2, idxs3, idxs4, coeffs1, coeffs2, coeffs3, coeffs4])
            intertable = np.rec.fromarrays((indexes, coeffs), names=('indexes', 'coeffs'))
            # saving interpolation lookup table
            np.save(intertable_name, intertable)
            self.update_intertable_conf(intertable, intertable_id, intertable_name, v.shape)

        else:
            raise ApplicationException.get_programmatic_exc(NO_INTERTABLE_CREATED, details=intertable_name)
        result[xs, ys] = v[idxs1] * coeffs1 + v[idxs2] * coeffs2 + v[idxs3] * coeffs3 + v[idxs4] * coeffs4
        return result, existing_intertable

    def update_intertable_conf(self, intertable, intertable_id, intertable_name, source_shape):
        self._LOADED_INTERTABLES[intertable_name] = intertable
        self.intertables_dict[intertable_id] = {'filename': util.files.filename(intertable_name),
                                                'method': self._mode,
                                                'source_shape': source_shape,
                                                'target_shape': self._target_coords.longs.shape}
        self.intertables_config.dump(self.intertables_dict)

    # set aux gids for grib interlookup creation
    def aux_for_intertable_generation(self, aux_g, aux_v, aux_g2, aux_v2):
        self._aux_gid = aux_g
        self._aux_val = aux_v
        self._aux_2nd_res_gid = aux_g2
        self._aux_2nd_res_val = aux_v2

    def set_mv_input(self, mv):
        self._mv_grib = mv

    @property
    def mv_output(self):
        return self._mv_efas

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)
