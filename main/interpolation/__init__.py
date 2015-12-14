import os

import numpy as np

import util.files
from main.exceptions import ApplicationException, NO_INTERTABLE_CREATED
from main.interpolation import scipy_interpolation_lib as ID
from main.interpolation.grib_interpolation_lib import grib_nearest, grib_invdist
from main.interpolation.latlong import LatLong
from main.interpolation.scipy_interpolation_lib import InverseDistance
from util.logger import Logger
from util.numeric import mask_it


class Interpolator(object):

    _suffix_scipy = '_scipy_'
    _prefix = 'I'

    scipy_modes_nnear = {'nearest': 1, 'invdist': 8}

    def __init__(self, exec_ctx):
        self._mode = exec_ctx.get('interpolation.mode')
        self._logger = Logger.get_logger()
        self._intertable_dir = exec_ctx.get('interpolation.dir')
        self._target_coords = LatLong(exec_ctx.get('interpolation.latMap'), exec_ctx.get('interpolation.lonMap'))
        self._mv_efas = self._target_coords.missing_value
        self._mv_grib = -1

        # values used for interpolation table computation
        self._aux_val = None
        self._aux_gid = None
        self._aux_2nd_res_gid = None
        self._aux_2nd_res_val = None

        self.create_if_missing = exec_ctx.get('interpolation.create')
        self.grib_methods = {'grib_nearest': self.grib_nearest, 'grib_invdist': self.grib_inverse_distance}

    @staticmethod
    def _read_intertable(intertable_name):
        intertable = np.load(intertable_name)
        if intertable_name.endswith('_nn.npy'):
            # grib nearest neighbour table
            return intertable[0], intertable[1], intertable[2]
        elif intertable_name.endswith('_inv.npy'):
            # grib inverse distance table
            return intertable[0], intertable[1], intertable[2], intertable[3], intertable[4], intertable[5], intertable[6], intertable[7], intertable[8], intertable[9]
        elif Interpolator._suffix_scipy in intertable_name:
            # return weighted distances (only used with nnear=8) and indexes
            return intertable[0], intertable[1]

    @staticmethod
    def _interpolate_scipy_invdist(z, _mv_grib, weights, indexes, nnear):

        # TODO CHECK: maybe we don't need to mask here
        z = mask_it(z, _mv_grib)
        if nnear == 1:
            # for nnear = 1 it doesn't care at this point if indexes come from intertable
            # or were just queried from the tree
            result = z[indexes.astype(int, copy=False)]
        else:
            result = np.einsum('ij,ij->i', weights, z[indexes.astype(int, copy=False)])
        return result

    def interpolate_scipy(self, latgrib, longrib, z, grid_id, grid_details=None, log_intertable=False):

        lonefas = self._target_coords.longs
        latefas = self._target_coords.lats
        intertable_name = self._intertable_name(grid_id, suffix=self._suffix_scipy + self._mode)

        orig_shape = lonefas.shape
        nnear = self.scipy_modes_nnear[self._mode]

        if util.files.exists(intertable_name):
            if log_intertable:
                # first interpolation: we want to log filename
                self._log('Using interpolation table: {}'.format(intertable_name), 'INFO')
            weights, indexes = self._read_intertable(intertable_name)
            result = self._interpolate_scipy_invdist(z, self._mv_grib, weights, indexes, nnear)
            grid_data = result.reshape(orig_shape)

        elif self.create_if_missing:
            assert grid_details is not None
            if latgrib is None:
                self._log('Trying to interpolate without grib lat/lons. Probably a geopotential grib!', 'ERROR')
                raise ApplicationException.get_programmatic_exc(5000)

            self._log('\nInterpolating table not found. Will create file: {}'.format(intertable_name), 'INFO')
            # import ipdb
            # ipdb.set_trace()
            invdisttree = InverseDistance(longrib, latgrib, grid_details, z.ravel(), self._mv_efas, self._mv_grib)
            result, weights, indexes = invdisttree.interpolate(lonefas, latefas, nnear)
            # saving interpolation lookup table
            np.save(intertable_name, np.asarray([weights, indexes], dtype=np.float64))
            # reshape to target (e.g. efas, glofas...)
            grid_data = result.reshape(orig_shape)

        else:
            raise ApplicationException.get_programmatic_exc(NO_INTERTABLE_CREATED, details=intertable_name)

        return grid_data

    # #### GRIB API INTERPOLATION ####################
    def interpolate_grib(self, v, gid, grid_id, log_intertable=False, second_spatial_resolution=False):
        return self.grib_methods[self._mode](v, gid, grid_id,
                                             log_intertable=log_intertable,
                                             second_spatial_resolution=second_spatial_resolution)
        # if self._mode == 'grib_nearest':
        #     return self.grib_nearest(v, gid, grid_id, log_intertable=log_intertable, second_spatial_resolution=second_spatial_resolution)
        # elif self._mode == 'grib_invdist':
        #     return self.grib_inverse_distance(v, gid, grid_id, log_intertable=log_intertable, second_spatial_resolution=second_spatial_resolution)

    def grib_nearest(self, v, gid, grid_id, log_intertable=False, second_spatial_resolution=False):
        intertable_name = self._intertable_name(grid_id, suffix='_nn')
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
            if log_intertable:
                # first interpolation: we want to log filename
                self._log('Using interpolation table: {}'.format(intertable_name), 'INFO')

            xs, ys, idxs = self._read_intertable(intertable_name)

            # TODO CHECK: maybe we don't need to mask here
            v = mask_it(v, self._mv_grib)

        elif self.create_if_missing:
            try:
                assert gid != -1, 'GRIB message reference was not found.'
            except AssertionError as e:
                raise ApplicationException.get_programmatic_exc(6000, details=str(e))
            self._log('\nInterpolating table not found. Will create file: {}'.format(intertable_name), 'INFO')
            xs, ys, idxs = grib_nearest(gid, self._target_coords.lats, self._target_coords.longs, self._target_coords.missing_value)
            intertable = np.asarray([xs, ys, idxs])
            np.save(intertable_name, intertable)
        else:
            raise ApplicationException.get_programmatic_exc(NO_INTERTABLE_CREATED, details=intertable_name)

        result[xs, ys] = v[idxs]
        return result, existing_intertable

    def grib_inverse_distance(self, v, gid, grid_id, log_intertable=False, second_spatial_resolution=False):
        intertable_name = self._intertable_name(grid_id, suffix='_inv')

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
            if log_intertable:
                # first interpolation: we want to log filename
                self._log('Using interpolation table: {}'.format(intertable_name), 'INFO')
            xs, ys, idxs1, idxs2, idxs3, idxs4, coeffs1, coeffs2, coeffs3, coeffs4 = self._read_intertable(intertable_name)
        elif self.create_if_missing:
            # assert...
            if gid == -1:
                raise ApplicationException.get_programmatic_exc(6000)
            self._log('\nInterpolating table not found. Will create file: {}'.format(intertable_name), 'INFO')
            lonefas = self._target_coords.longs
            latefas = self._target_coords.lats
            mv = self._target_coords.missing_value
            xs, ys, idxs1, idxs2, idxs3, idxs4, coeffs1, coeffs2, coeffs3, coeffs4 = grib_invdist(gid, latefas, lonefas, mv)
            intertable = np.asarray([xs, ys, idxs1, idxs2, idxs3, idxs4, coeffs1, coeffs2, coeffs3, coeffs4])
            # saving interpolation lookup table
            np.save(intertable_name, intertable)
        else:
            raise ApplicationException.get_programmatic_exc(NO_INTERTABLE_CREATED, details=intertable_name)
        result[xs, ys] = v[idxs1] * coeffs1 + v[idxs2] * coeffs2 + \
            v[idxs3] * coeffs3 + v[idxs4] * coeffs4
        return result, existing_intertable

    def _intertable_name(self, grid_id, suffix):
        name = '{}{}_{}{}.npy'.format(self._prefix, grid_id.replace('$', '_'), self._target_coords.identifier, suffix)
        return os.path.normpath(os.path.join(self._intertable_dir, name))

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
