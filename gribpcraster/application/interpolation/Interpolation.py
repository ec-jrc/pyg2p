import os
import numpy as np
from gribpcraster.application.interpolation.grib_interpolation_lib import _grib_nearest, _grib_invdist
from util.numeric.numeric import _mask_it
from util.logger.Logger import Logger
import util.file.FileManager as fm
from gribpcraster.application.interpolation.LatLongDem import LatLongBuffer
import InverseDistance as ID
from InverseDistance import InverseDistance
from gribpcraster.exc.ApplicationException import ApplicationException
import gribpcraster

__author__ = "domenico nappo"
__date__ = "$Jun 13, 2014 12:22 AM$"


dir_ = os.path.dirname(gribpcraster.__file__)
#default intertable dir. Can be overwritten with intertableDir xml/CLI parameter
INTERTABLES_DIR = os.path.join(dir_, '../', 'configuration/intertables/')
TAB_NAME_SCIPY = '_scipy_'
SAFE_PREFIX_INTTAB_NAME = 'I'


def _read_intertable(intertable_name, log=None):
    if log is not None:
        #first interpolation table usage
        #log filename interpolation table
        log('Using interpolation table: %s' % intertable_name, 'INFO')
    intertable = np.load(intertable_name)
    if intertable_name.endswith('_nn.npy'):
        return intertable[0], intertable[1], intertable[2]
    elif intertable_name.endswith('_inv.npy'):
        return intertable[0], intertable[1], intertable[2], intertable[3], intertable[4], intertable[5], intertable[6], intertable[7], intertable[8], intertable[9]
    elif TAB_NAME_SCIPY in intertable_name:
        #return w/distances, indexes
        return intertable[0], intertable[1]


class Interpolator:

    modes_nnear = {'nearest': 1, 'invdist': 8}

    def __init__(self, exec_ctx, radius=6367470.0):
        self._mode = exec_ctx.get('interpolation.mode')
        self._logger = Logger('Interpolator', loggingLevel=exec_ctx.get('logger.level'))
        self._intertable_dir = INTERTABLES_DIR if exec_ctx.get('interpolation.dir') is None else exec_ctx.get('interpolation.dir')
        if self._mode in ['invdist', 'nearest']:
            self._radius = radius
        _latMap = exec_ctx.get('interpolation.latMap')
        _lonMap = exec_ctx.get('interpolation.lonMap')
        self._latLongBuffer = LatLongBuffer(_latMap, _lonMap)
        self._mvEfas = self._latLongBuffer.getMissingValue()
        self._mvGrib = -1

        self._aux_val = None
        self._aux_gid = None
        self._aux_2nd_res_gid = None
        self._aux_2nd_res_val = None

    def set_radius(self, r):
        self._radius = r

    def setMissingValueGrib(self, mv):
        self._mvGrib = mv

    def getMissingValueGrib(self):
        return self._mvGrib

    def getMissingValueEfas(self):
        return self._mvEfas

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def interpolate_scipy(self, latgrib, longrib, f, grid_id, log_intertable=False):

        lonefas = self._latLongBuffer.getLong()
        latefas = self._latLongBuffer.getLat()

        intertable_name = os.path.normpath(os.path.join(self._intertable_dir, SAFE_PREFIX_INTTAB_NAME + grid_id.replace('$','_')+'_'+self._latLongBuffer.getId()+TAB_NAME_SCIPY+self._mode+'.npy'))
        log = self._log if log_intertable else None
        orig_shape = lonefas.shape
        #parameters
        nnear = Interpolator.modes_nnear[self._mode]
        if fm.exists(intertable_name):
            dists, indexes = _read_intertable(intertable_name, log=log)
            result = ID.interpolate_invdist(f, self._mvGrib, self._mvEfas, dists, indexes, nnear, from_inter=True)
            grid_data = result.reshape(orig_shape)
        else:
            if latgrib is None and longrib is None:
                self._log('Trying to interpolate without grib lat/lons. Probably a geopotential grib!','ERROR')
                raise ApplicationException.get_programmatic_exc(5000)

            self._log('Interpolating table not found. Will create file: ' + intertable_name, 'INFO')
            invdisttree = InverseDistance(longrib, latgrib, self._radius, f.ravel(), self._mvEfas, self._mvGrib)
            result, dists, indexes = invdisttree(lonefas, latefas, nnear)
            #saving interpolation lookup table
            np.save(intertable_name, np.array([dists, indexes], dtype=np.float64))
            #reshape to efas
            grid_data = result.reshape(orig_shape)

        return grid_data

    ##### GRIB API INTERPOLATION ####################
    def interpolate_grib(self, v, gid, grid_id, log_intertable=False, second_spatial_resolution=False):

        if self._mode == 'grib_nearest':
            return self.grib_nearest(v, gid, grid_id, log_intertable=log_intertable, second_spatial_resolution=second_spatial_resolution)
        elif self._mode == 'grib_invdist':
            return self.grib_inverse_distance(v, gid, grid_id, log_intertable=log_intertable, second_spatial_resolution=second_spatial_resolution)

    def grib_nearest(self, v, gid, grid_id, log_intertable=False, second_spatial_resolution=False):

        intertable_name = os.path.normpath(os.path.join(self._intertable_dir, SAFE_PREFIX_INTTAB_NAME+grid_id.replace('$', '_')+'_'+self._latLongBuffer.getId()+'_nn.npy'))
        existing_intertable = False
        result = np.empty(self._latLongBuffer.getLong().shape)
        result.fill(self._mvEfas)
        result = _mask_it(result, self._mvEfas)
        if gid == -1 and not fm.exists(intertable_name):
            #here it should:
            #aux_gid and aux_values are only used to create the interlookuptable
            self._log('Creating lookup table using aux message')
            if second_spatial_resolution:
                self.grib_nearest(self._aux_2nd_res_val, self._aux_2nd_res_gid, grid_id, second_spatial_resolution=second_spatial_resolution)
            else:
                self.grib_nearest(self._aux_val, self._aux_gid, grid_id)

        if fm.exists(intertable_name):
            #interpolation using intertables
            existing_intertable = True
            log = self._log if log_intertable else None
            xs, ys, idxs = _read_intertable(intertable_name, log=log)
            v = _mask_it(v, self._mvGrib)
        else:
            #assert...
            if gid == -1:
                raise ApplicationException.get_programmatic_exc(6000)
            self._log('Interpolating table not found. Will create file: ' + intertable_name, 'INFO')
            lonefas = self._latLongBuffer.getLong()
            latefas = self._latLongBuffer.getLat()
            mv = self._latLongBuffer.getMissingValue()
            # xs, ys, idxs, result = _grib_nearest(gid, latefas, lonefas, mv, result)
            xs, ys, idxs = _grib_nearest(gid, latefas, lonefas, mv, result)
            intertable = np.array([xs, ys, idxs])
            #saving interpolation lookup table
            np.save(intertable_name, intertable)

        result[xs.astype(int, copy=False), ys.astype(int, copy=False)] = v[idxs.astype(int, copy=False)]
        return result, existing_intertable

    def grib_inverse_distance(self, v, gid, grid_id, log_intertable=False, second_spatial_resolution=False):

        intertable_name = os.path.normpath(os.path.join(self._intertable_dir, SAFE_PREFIX_INTTAB_NAME + grid_id.replace('$','_')+'_'+self._latLongBuffer.getId()+'_inv.npy'))
        result = np.empty(self._latLongBuffer.getLong().shape)
        result.fill(self._mvEfas)
        result = np.ma.masked_array(data=result, fill_value=self._mvEfas, copy=False)
        v = _mask_it(v, self._mvGrib)
        existing_intertable = False
        log = self._log if log_intertable else None
        #check of gid is due to the recursive call
        if gid == -1 and (not os.path.exists(intertable_name) or not os.path.isfile(intertable_name)):
            #aux_gid and aux_values are only used to create the interlookuptable
            #since manipulated values messages don't have gid reference to grib file any longer
            self._log('Creating lookup table using aux message')
            if second_spatial_resolution:
                self.grib_inverse_distance(self._aux_2nd_res_val, self._aux_2nd_res_gid, grid_id, second_spatial_resolution=second_spatial_resolution)
            else:
                self.grib_inverse_distance(self._aux_val, self._aux_gid, grid_id)

        if fm.exists(intertable_name):
            #interpolation using intertables
            existing_intertable = True
            self._log('Interpolating with table ' + intertable_name)
            xs, ys, idxs1, idxs2, idxs3, idxs4, coeffs1, coeffs2, coeffs3, coeffs4 = _read_intertable(intertable_name, log=log)

        else:
            #assert...
            if gid == -1:
                raise ApplicationException.get_programmatic_exc(6000)
            self._log('Interpolating table not found. Will create file: '+intertable_name, 'INFO')
            lonefas = self._latLongBuffer.getLong()
            latefas = self._latLongBuffer.getLat()
            mv = self._latLongBuffer.getMissingValue()
            xs, ys, idxs1, idxs2, idxs3, idxs4, coeffs1, coeffs2, coeffs3, coeffs4 = _grib_invdist(gid, latefas, lonefas, mv, result)
            intertable = np.array([xs, ys, idxs1, idxs2, idxs3, idxs4, coeffs1, coeffs2, coeffs3, coeffs4])
            #saving interpolation lookup table
            np.save(intertable_name, intertable)

        result[xs.astype(int, copy=False), ys.astype(int, copy=False)] = v[idxs1.astype(int, copy=False)] * coeffs1 + v[idxs2.astype(int, copy=False)] * coeffs2 + \
            v[idxs3.astype(int, copy=False)] * coeffs3 + v[idxs4.astype(int, copy=False)] * coeffs4
        return result, existing_intertable

    #aux gid for grib interlookup creation
    def setAuxToCreateLookup(self, aux_g, aux_v, aux_g2, aux_v2):
        self._aux_gid = aux_g
        self._aux_val = aux_v
        self._aux_2nd_res_gid = aux_g2
        self._aux_2nd_res_val = aux_v2