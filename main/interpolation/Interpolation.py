import os

import numpy as np

import InverseDistance as ID
import util.files
from InverseDistance import InverseDistance
from main.exceptions import ApplicationException, NO_INTERTABLE_CREATED
from .latlong import LatLong
from .grib_interpolation_lib import grib_nearest, grib_invdist
from util.logger import Logger
from util.numeric import mask_it


def _read_intertable(intertable_name, log=None):
    if log is not None:
        # first interpolation table usage
        # log filename interpolation table
        log('Using interpolation table: %s' % intertable_name, 'INFO')
    intertable = np.load(intertable_name)
    if intertable_name.endswith('_nn.npy'):
        return intertable[0], intertable[1], intertable[2]
    elif intertable_name.endswith('_inv.npy'):
        return intertable[0], intertable[1], intertable[2], intertable[3], intertable[4], intertable[5], intertable[6], intertable[7], intertable[8], intertable[9]
    elif Interpolator.tabname_scipy in intertable_name:
        # return w/distances, indexes
        return intertable[0], intertable[1]


class Interpolator:

    tabname_scipy = '_scipy_'
    _prefix = 'I'

    modes_nnear = {'nearest': 1, 'invdist': 8}

    def __init__(self, exec_ctx, radius=6367470.0):
        self._mode = exec_ctx.get('interpolation.mode')
        self._logger = Logger.get_logger()
        self._intertable_dir = exec_ctx.get('interpolation.dir')
        if self._mode in ['invdist', 'nearest']:
            self._radius = radius
        _latMap = exec_ctx.get('interpolation.latMap')
        _lonMap = exec_ctx.get('interpolation.lonMap')
        self._latlons = LatLong(_latMap, _lonMap)
        self._mvEfas = self._latlons.missing_value
        self._mvGrib = -1

        self._aux_val = None
        self._aux_gid = None
        self._aux_2nd_res_gid = None
        self._aux_2nd_res_val = None
        self.create_if_missing = exec_ctx.get('interpolation.create')

    def _intertable_name(self, grid_id, suffix):
        name = '{}{}_{}{}.npy'.format(self._prefix, grid_id.replace('$', '_'), self._latlons.identifier, suffix)
        return os.path.normpath(os.path.join(self._intertable_dir, name))

    def set_radius(self, r):
        self._radius = r

    def set_mv_input(self, mv):
        self._mvGrib = mv

    def mv_input(self):
        return self._mvGrib

    def mv_output(self):
        return self._mvEfas

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def interpolate_scipy(self, latgrib, longrib, f, grid_id, log_intertable=False):

        lonefas = self._latlons.longs
        latefas = self._latlons.lats
        intertable_name = self._intertable_name(grid_id, suffix=self.tabname_scipy + self._mode)

        # intertable_name = os.path.normpath(os.path.join(self._intertable_dir, self._prefix + grid_id.replace('$', '_') + '_' + self._latLongBuffer.identifier + self.tabname_scipy + self._mode + '.npy'))
        orig_shape = lonefas.shape
        # parameters
        nnear = Interpolator.modes_nnear[self._mode]

        if util.files.exists(intertable_name):
            log = self._log if log_intertable else None
            dists, indexes = _read_intertable(intertable_name, log=log)
            result = ID.interpolate_invdist(f, self._mvGrib, self._mvEfas, dists, indexes, nnear, from_inter=True)
            grid_data = result.reshape(orig_shape)

        elif self.create_if_missing:
            if latgrib is None and longrib is None:
                self._log('Trying to interpolate without grib lat/lons. Probably a geopotential grib!','ERROR')
                raise ApplicationException.get_programmatic_exc(5000)

            self._log('Interpolating table not found. Will create file: ' + intertable_name, 'INFO')
            invdisttree = InverseDistance(longrib, latgrib, self._radius, f.ravel(), self._mvEfas, self._mvGrib)
            result, dists, indexes = invdisttree(lonefas, latefas, nnear)
            # saving interpolation lookup table
            np.save(intertable_name, np.array([dists, indexes], dtype=np.float64))
            # reshape to efas
            grid_data = result.reshape(orig_shape)

        else:
            raise ApplicationException.get_programmatic_exc(NO_INTERTABLE_CREATED, details=intertable_name)

        return grid_data

    # #### GRIB API INTERPOLATION ####################
    def interpolate_grib(self, v, gid, grid_id, log_intertable=False, second_spatial_resolution=False):

        if self._mode == 'grib_nearest':
            return self.grib_nearest(v, gid, grid_id, log_intertable=log_intertable, second_spatial_resolution=second_spatial_resolution)
        elif self._mode == 'grib_invdist':
            return self.grib_inverse_distance(v, gid, grid_id, log_intertable=log_intertable, second_spatial_resolution=second_spatial_resolution)

    def grib_nearest(self, v, gid, grid_id, log_intertable=False, second_spatial_resolution=False):
        intertable_name = self._intertable_name(grid_id, suffix='_nn')
        # intertable_name = os.path.normpath(os.path.join(self._intertable_dir, self._prefix + grid_id.replace('$', '_') + '_' + self._latLongBuffer.identifier + '_nn.npy'))
        existing_intertable = False
        result = np.empty(self._latlons.longs.shape)
        result.fill(self._mvEfas)
        result = mask_it(result, self._mvEfas)
        if gid == -1 and not util.files.exists(intertable_name):
            # aux_gid and aux_values are only used to create the interlookuptable
            self._log('Creating lookup table using aux message')
            if second_spatial_resolution:
                self.grib_nearest(self._aux_2nd_res_val, self._aux_2nd_res_gid, grid_id, second_spatial_resolution=second_spatial_resolution)
            else:
                self.grib_nearest(self._aux_val, self._aux_gid, grid_id)

        if util.files.exists(intertable_name):
            # interpolation using intertables
            existing_intertable = True
            log = self._log if log_intertable else None
            xs, ys, idxs = _read_intertable(intertable_name, log=log)
            v = mask_it(v, self._mvGrib)
        elif self.create_if_missing:
            # assert...
            if gid == -1:
                raise ApplicationException.get_programmatic_exc(6000)
            self._log('Interpolating table not found. Will create file: ' + intertable_name, 'INFO')
            lonefas = self._latlons.longs
            latefas = self._latlons.lats
            mv = self._latlons.missing_value
            # xs, ys, idxs, result = _grib_nearest(gid, latefas, lonefas, mv, result)
            xs, ys, idxs = grib_nearest(gid, latefas, lonefas, mv, result)
            intertable = np.array([xs, ys, idxs])
            # saving interpolation lookup table
            np.save(intertable_name, intertable)
        else:
            raise ApplicationException.get_programmatic_exc(NO_INTERTABLE_CREATED, details=intertable_name)

        result[xs.astype(int, copy=False), ys.astype(int, copy=False)] = v[idxs.astype(int, copy=False)]
        return result, existing_intertable

    def grib_inverse_distance(self, v, gid, grid_id, log_intertable=False, second_spatial_resolution=False):
        intertable_name = self._intertable_name(grid_id, suffix='_inv')
        # intertable_name = os.path.normpath(os.path.join(self._intertable_dir, self._prefix + grid_id.replace('$', '_') + '_' + self._latLongBuffer.identifier + '_inv.npy'))
        result = np.empty(self._latlons.longs.shape)
        result.fill(self._mvEfas)
        result = np.ma.masked_array(data=result, fill_value=self._mvEfas, copy=False)
        v = mask_it(v, self._mvGrib)
        existing_intertable = False
        log = self._log if log_intertable else None
        # check of gid is due to the recursive call
        if gid == -1 and (not os.path.exists(intertable_name) or not os.path.isfile(intertable_name)):
            # aux_gid and aux_values are only used to create the interlookuptable
            # since manipulated values messages don't have gid reference to grib file any longer
            self._log('Creating lookup table using aux message')
            if second_spatial_resolution:
                self.grib_inverse_distance(self._aux_2nd_res_val, self._aux_2nd_res_gid, grid_id, second_spatial_resolution=second_spatial_resolution)
            else:
                self.grib_inverse_distance(self._aux_val, self._aux_gid, grid_id)

        if util.files.exists(intertable_name):
            # interpolation using intertables
            existing_intertable = True
            self._log('Interpolating with table ' + intertable_name)
            xs, ys, idxs1, idxs2, idxs3, idxs4, coeffs1, coeffs2, coeffs3, coeffs4 = _read_intertable(intertable_name, log=log)
        elif self.create_if_missing:
            # assert...
            if gid == -1:
                raise ApplicationException.get_programmatic_exc(6000)
            self._log('Interpolating table not found. Will create file: ' + intertable_name, 'INFO')
            lonefas = self._latlons.longs
            latefas = self._latlons.lats
            mv = self._latlons.missing_value
            xs, ys, idxs1, idxs2, idxs3, idxs4, coeffs1, coeffs2, coeffs3, coeffs4 = grib_invdist(gid, latefas, lonefas, mv, result)
            intertable = np.array([xs, ys, idxs1, idxs2, idxs3, idxs4, coeffs1, coeffs2, coeffs3, coeffs4])
            # saving interpolation lookup table
            np.save(intertable_name, intertable)
        else:
            raise ApplicationException.get_programmatic_exc(NO_INTERTABLE_CREATED, details=intertable_name)

        result[xs.astype(int, copy=False), ys.astype(int, copy=False)] = v[idxs1.astype(int, copy=False)] * coeffs1 + v[idxs2.astype(int, copy=False)] * coeffs2 + \
            v[idxs3.astype(int, copy=False)] * coeffs3 + v[idxs4.astype(int, copy=False)] * coeffs4
        return result, existing_intertable

    # aux gid for grib interlookup creation
    def aux_for_intertable_generation(self, aux_g, aux_v, aux_g2, aux_v2):
        self._aux_gid = aux_g
        self._aux_val = aux_v
        self._aux_2nd_res_gid = aux_g2
        self._aux_2nd_res_val = aux_v2
