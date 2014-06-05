from gribpcraster.application.interpolation.grib_interpolation_lib import _grib_nearest, _grib_invdist
from util.numeric.numeric import _mask_it

__author__ = "nappodo"
__date__ = "$Feb 17, 2013 10:46:41 AM$"

import scipy.interpolate
import os

import numpy as np
from util.logger.Logger import Logger
import util.file.FileManager as fm
from gribpcraster.application.interpolation.LatLongDem import LatLongBuffer
import InverseDistance as ID
from InverseDistance import InverseDistance
from gribpcraster.exc.ApplicationException import ApplicationException
import gribpcraster
dir_ = os.path.dirname(gribpcraster.__file__)
#default intertable dir. Can be overwritten with intertableDir xml/CLI parameter
INTERTABLES_DIR = os.path.join(dir_, '../', 'configuration/intertables/')
TAB_NAME_SCIPY = '_scipy_'
SAFE_PREFIX_INTTAB_NAME = 'I'

def _read_intertable(intertable_name, log=None):
    if log is not None:
        #first interpolation table usage
        #log filename interpolation table
        log('Using interpolation table: %s'%(intertable_name), 'INFO')
    intertable = np.load(intertable_name)
    if intertable_name.endswith('_nn.npy'):
        return intertable[0], intertable[1], intertable[2]
    elif intertable_name.endswith('_inv.npy'):
        return intertable[0], intertable[1], intertable[2], intertable[3], intertable[4], intertable[5],intertable[6], intertable[7], intertable[8], intertable[9]
    elif TAB_NAME_SCIPY in intertable_name:
        #return distances, indexes
        return intertable[0], intertable[1]


#returning numpy arrays: x, y of efas arrays and idx of grib values array and value

class Interpolator:
    def __init__(self, execCtx):
        self._mode = execCtx.get('interpolation.mode')
        self._logger = Logger('Interpolator', loggingLevel=execCtx.get('logger.level'))
        self._intertable_dir = INTERTABLES_DIR if execCtx.get('interpolation.dir') is None else execCtx.get('interpolation.dir')
        #setting additional interpolation parameters for some methods
        if self._mode == 'griddata':
            self._method = execCtx.get('griddata.method')
        elif self._mode in ['invdist', 'nearest']:
            self._leafsize=execCtx.get(self._mode + '.leafsize')
            self._p = execCtx.get(self._mode + '.p')
            self._eps = execCtx.get(self._mode + '.eps')

        _latMap = execCtx.get('interpolation.latMap')
        _lonMap = execCtx.get('interpolation.lonMap')
        self._latLongBuffer = LatLongBuffer(_latMap, _lonMap)
        self._mvEfas = self._latLongBuffer.getMissingValue()
        self._mvGrib = -1

        self._aux_val = None
        self._aux_gid = -1
        self._aux_2nd_res_gid = None
        self._aux_2nd_res_val = -1

    def setMissingValueGrib(self, mv):
        self._mvGrib = mv

    def getMissingValueGrib(self):
        return self._mvGrib

    def getMissingValueEfas(self):
        return self._mvEfas

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def interpolate_with_scipy(self, yp, xp, f, grid_id, log_intertable=False):
        if self._mode == 'griddata':
            return self.interpolateGriddata(yp, xp, f)
        elif self._mode in ['invdist', 'nearest']:
            return self.interpolate_kdtree(yp, xp, f, grid_id, log_intertable=log_intertable)

    def interpolate_kdtree(self, latgrib, longrib, f, grid_id, log_intertable=False):

        lonefas = lonefas_w_mv = self._latLongBuffer.getLong()
        latefas = self._latLongBuffer.getLat()
        orig_shape = lonefas_w_mv.shape
         #parameters
        nnear = 1
        if self._mode == 'nearest':
            self._log('Interpolating with nearest neighbour ')
        elif self._mode == 'invdist':
            nnear = 8
            self._log('Interpolating with inverse distance ')
        intertable_name = os.path.join(self._intertable_dir, SAFE_PREFIX_INTTAB_NAME + grid_id.replace('$','_')+'_'+self._latLongBuffer.getId()+TAB_NAME_SCIPY+self._mode+'.npy')
        log = self._log if log_intertable else None
        if fm.exists(intertable_name):
            dists, indexes = _read_intertable(intertable_name, log=log)
            result = ID.interpolate_invdist(f, self._mvEfas, dists, indexes, nnear, self._p, from_inter=True)
            grid_data = result.reshape(orig_shape)
        else:
            if latgrib is None and longrib is None:
                self._log('Trying to interpolate without grib lat/lons. Probably a geopotential grib!','ERROR')
                raise ApplicationException.get_programmatic_exc(5000)

            self._log('Interpolating table not found. Will create file: ' + intertable_name, 'INFO')
            data_locations = np.vstack((longrib.ravel(), latgrib.ravel())).T
            efas_locations = np.vstack((lonefas.ravel(), latefas.ravel())).T
            invdisttree = InverseDistance(data_locations, f.ravel(), self._mvEfas, self._mvGrib, leafsize=self._leafsize)
            result, dists, indexes = invdisttree(efas_locations, eps=self._eps, p=self._p, mode=self._mode)
            self._log('interpolation done')
            intertable = np.array([dists, indexes], dtype=np.float64)
            #saving interpolation lookup table
            np.save(intertable_name, intertable)
            #reshape to efas
            grid_data = result.reshape(orig_shape)

        return grid_data


    def interpolateGriddata(self, yp, xp, f):

        latgrib = yp
        longrib = xp

        xi = self._latLongBuffer.getLong()
        yi = self._latLongBuffer.getLat()
        origShape = xi.shape

        latefas=yi
        lonefas=xi

        data_locations = np.vstack((longrib.ravel(),latgrib.ravel())).T
        grid_locations = np.vstack((lonefas.ravel(),latefas.ravel())).T
        self._log('interpolating with griddata: '+self._method)
        grid_data      = scipy.interpolate.griddata(data_locations, f.ravel(),
                                                    grid_locations,
                                                    method=self._method)
        self._log('interpolation done')

        grid_data=grid_data.reshape(origShape)
        return grid_data

    ##### GRIB API INTERPOLATION ####################

    def interpolate_grib(self, v, gid, grid_id, log_intertable=False, second_spatial_resolution=False):
        if self._mode == 'grib_nearest':
            return self.interpolateGribNearest(v, gid, grid_id, log_intertable=log_intertable, second_spatial_resolution=second_spatial_resolution)
        elif self._mode == 'grib_invdist':
            return self.interpolateGribInvDist(v, gid, grid_id, log_intertable=log_intertable, second_spatial_resolution=second_spatial_resolution)

    def interpolateGribNearest(self, v, gid, grid_id, log_intertable=False, second_spatial_resolution=False):

        intertable_name = os.path.join(self._intertable_dir, SAFE_PREFIX_INTTAB_NAME+grid_id.replace('$', '_')+'_'+self._latLongBuffer.getId()+'_nn.npy')
        existing_intertable = False
        result = np.empty(self._latLongBuffer.getLong().shape)
        result.fill(self._mvEfas)
        result = _mask_it(result, self._mvEfas)
        if gid == -1 and (not os.path.exists(intertable_name) or not os.path.isfile(intertable_name)):
            #here it should:
            #aux_gid and aux_values are only used to create the interlookuptable
            self._log('Creating lookup table using aux message')
            if second_spatial_resolution:
                self.interpolateGribNearest(self._aux_2nd_res_val, self._aux_2nd_res_gid, grid_id, second_spatial_resolution=second_spatial_resolution)
            else:
                self.interpolateGribNearest(self._aux_val, self._aux_gid, grid_id)

        if fm.exists(intertable_name):
            existing_intertable = True
            log = self._log if log_intertable else None
            xs, ys, idxs = _read_intertable(intertable_name, log=log)
            v = _mask_it(v, self._mvGrib)
            result[xs.astype(int, copy=False), ys.astype(int, copy=False)] = v[idxs.astype(int, copy=False)]
        else:
            #assert...
            if gid == -1:
                raise ApplicationException.get_programmatic_exc(6000)
            self._log('Interpolating table not found. Will create file: '+intertable_name, 'INFO')
            lonefas = self._latLongBuffer.getLong()
            latefas = self._latLongBuffer.getLat()
            mv = self._latLongBuffer.getMissingValue()
            xs, ys, idxs, result = _grib_nearest(gid, latefas, lonefas, mv, result)
            intertable = np.array([xs, ys, idxs])
            #saving interpolation lookup table
            np.save(intertable_name, intertable)

        return result, existing_intertable

    def interpolateGribInvDist(self, v, gid, grid_id, iMap=0, log_intertable=False, second_spatial_resolution=False):
        intertable_name = os.path.join(self._intertable_dir, SAFE_PREFIX_INTTAB_NAME+grid_id.replace('$','_')+'_'+self._latLongBuffer.getId()+'_inv.npy')
        result = np.empty(self._latLongBuffer.getLong().shape)
        result.fill(self._mvEfas)
        result = np.ma.masked_array(data=result, fill_value=self._mvEfas, copy=False)
        v = _mask_it(v, self._mvGrib)

        log = self._log if log_intertable else None
        #check of gid is due to the recursive call
        if gid == -1 and (not os.path.exists(intertable_name) or not os.path.isfile(intertable_name)):
            #aux_gid and aux_values are only used to create the interlookuptable
            #since manipulated values messages don't have gid reference to grib file any longer
            self._log('Creating lookup table using aux message')
            if second_spatial_resolution:
                self.interpolateGribInvDist(self._aux_2nd_res_val, self._aux_2nd_res_gid, grid_id, second_spatial_resolution=second_spatial_resolution)
            else:
                self.interpolateGribInvDist(self._aux_val, self._aux_gid, grid_id)

        if os.path.exists(intertable_name) and os.path.isfile(intertable_name):
            self._log('Interpolating with table ' + intertable_name)
            xs, ys, idxs1, idxs2, idxs3, idxs4, coeffs1, coeffs2, coeffs3, coeffs4 = _read_intertable(intertable_name, log=log)
            result[xs.astype(int, copy=False), ys.astype(int, copy=False)] = v[idxs1.astype(int, copy=False)] * coeffs1 + v[idxs2.astype(int, copy=False)] * coeffs2 + \
                                                     v[idxs3.astype(int, copy=False)] * coeffs3 + v[idxs4.astype(int, copy=False)] * coeffs4

            return result

        else:
            #assert...
            if gid == -1:
                raise ApplicationException.get_programmatic_exc(6000)
            self._log('Interpolating table not found. Will create file: '+intertable_name, 'INFO')
            lonefas = self._latLongBuffer.getLong()
            latefas = self._latLongBuffer.getLat()
            mv = self._latLongBuffer.getMissingValue()
            xs, ys, idxs1, idxs2, idxs3, idxs4, coeffs1, coeffs2, coeffs3, coeffs4, result = _grib_invdist(gid, latefas, lonefas, mv, result)
            intertable = np.array([xs, ys, idxs1, idxs2, idxs3, idxs4, coeffs1, coeffs2, coeffs3, coeffs4])
            #saving interpolation lookup table
            np.save(intertable_name, intertable)

        return result

    #aux gid for grib interlookup creation
    def setAuxToCreateLookup(self, aux_g, aux_v, aux_g2, aux_v2):
        self._aux_gid = aux_g
        self._aux_val = aux_v
        self._aux_2nd_res_gid = aux_g2
        self._aux_2nd_res_val = aux_v2