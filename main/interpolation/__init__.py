import os

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

    def __init__(self, exec_ctx):
        self._mode = exec_ctx.get('interpolation.mode')
        self._logger = Logger.get_logger()
        self._intertable_dir = exec_ctx.get('interpolation.dir')
        self._target_coords = LatLong(exec_ctx.get('interpolation.latMap'), exec_ctx.get('interpolation.lonMap'))
        self._mv_efas = self._target_coords.missing_value
        self._mv_grib = -1
        self.parallel = exec_ctx.get('interpolation.parallel')

        # values used for interpolation table computation
        self._aux_val = None
        self._aux_gid = None
        self._aux_2nd_res_gid = None
        self._aux_2nd_res_val = None

        self.create_if_missing = exec_ctx.get('interpolation.create')
        self.grib_methods = {'grib_nearest': self.grib_nearest, 'grib_invdist': self.grib_inverse_distance}

    def _read_intertable(self, intertable_name):

        if intertable_name not in self._LOADED_INTERTABLES:
            intertable = np.load(intertable_name)
            self._LOADED_INTERTABLES[intertable_name] = intertable
            self._log('Using interpolation table: {}'.format(intertable_name), 'INFO')
        else:
            intertable = self._LOADED_INTERTABLES[intertable_name]

        if intertable_name.endswith('_nn.npy'):
            # grib nearest neighbour table
            return intertable[0], intertable[1], intertable[2]
        elif intertable_name.endswith('_inv.npy'):
            # grib inverse distance table is a recorded numpy array with keys 'indexes' and 'coeffs'
            indexes = intertable['indexes']
            coeffs = intertable['coeffs']
            return indexes[0], indexes[1], indexes[2], indexes[3], indexes[4], indexes[5], coeffs[0], coeffs[1], coeffs[2], coeffs[3]
        elif Interpolator._suffix_scipy in intertable_name:
            # return weighted distances (only used with nnear=4) and indexes
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

    def interpolate_scipy(self, latgrib, longrib, z, grid_id, grid_details=None):

        lonefas = self._target_coords.longs
        latefas = self._target_coords.lats
        intertable_name = self._intertable_name(grid_id, suffix=self._suffix_scipy + self._mode)

        orig_shape = lonefas.shape
        nnear = self.scipy_modes_nnear[self._mode]

        if util.files.exists(intertable_name):
            weights, indexes = self._read_intertable(intertable_name)
            result = self._interpolate_scipy_invdist(z, self._mv_grib, weights, indexes, nnear)
            grid_data = result.reshape(orig_shape)

        elif self.create_if_missing:
            assert grid_details is not None
            if latgrib is None:
                self._log('Trying to interpolate without grib lat/lons. Probably a geopotential grib!', 'ERROR')
                raise ApplicationException.get_programmatic_exc(5000)

            self._log('\nInterpolating table not found. Will create file: {}'.format(intertable_name), 'INFO')
            invdisttree = InverseDistance(longrib, latgrib, grid_details, z.ravel(), self._mv_efas, self._mv_grib)
            result, weights, indexes = invdisttree.interpolate(lonefas, latefas, nnear, parallel=self.parallel)
            # saving interpolation lookup table
            np.save(intertable_name, np.asarray([weights, indexes], dtype=np.float64))
            # reshape to target (e.g. efas, glofas...)
            grid_data = result.reshape(orig_shape)

        else:
            raise ApplicationException.get_programmatic_exc(NO_INTERTABLE_CREATED, details=intertable_name)

        return grid_data

    # #### GRIB API INTERPOLATION ####################
    def interpolate_grib(self, v, gid, grid_id, second_spatial_resolution=False):
        return self.grib_methods[self._mode](v, gid, grid_id, second_spatial_resolution=second_spatial_resolution)

    def grib_nearest(self, v, gid, grid_id, second_spatial_resolution=False):
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
            xs, ys, idxs = self._read_intertable(intertable_name)

            # TODO CHECK: maybe we don't need to mask here
            v = mask_it(v, self._mv_grib)

        elif self.create_if_missing:
            try:
                assert gid != -1, 'GRIB message reference was not found.'
            except AssertionError as e:
                raise ApplicationException.get_programmatic_exc(6000, details=str(e))
            self._log('\nInterpolating table not found. Will create file: {}'.format(intertable_name), 'INFO')
            # xs, ys, idxs = grib_nearest(gid, self._target_coords.lats, self._target_coords.longs, self._target_coords.missing_value)
            xs, ys, idxs = getattr(grib_interpolation_lib, 'grib_nearest{}'.format('' if not self.parallel else '_parallel'))(gid, self._target_coords.lats, self._target_coords.longs, self._target_coords.missing_value)
            intertable = np.asarray([xs, ys, idxs])
            np.save(intertable_name, intertable)
            self._LOADED_INTERTABLES[intertable_name] = intertable
        else:
            raise ApplicationException.get_programmatic_exc(NO_INTERTABLE_CREATED, details=intertable_name)

        result[xs, ys] = v[idxs]
        return result, existing_intertable

    def grib_inverse_distance(self, v, gid, grid_id, second_spatial_resolution=False):
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
            self._LOADED_INTERTABLES[intertable_name] = intertable
        else:
            raise ApplicationException.get_programmatic_exc(NO_INTERTABLE_CREATED, details=intertable_name)
        result[xs, ys] = v[idxs1] * coeffs1 + v[idxs2] * coeffs2 + v[idxs3] * coeffs3 + v[idxs4] * coeffs4
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

    @classmethod
    def convert_intertables_to_v2(cls, path, logger):
        logger.attach_config_logger()
        logger.info('Looking into {}'.format(path))
        for f in os.listdir(path):
            filename_changed = False
            filepath = os.path.join(path, f)
            if '_M_' in util.files.file_name(filepath):
                logger.info('Skipped: {}'.format(util.files.file_name(filepath)))
                continue
            if util.files.is_dir(filepath):
                cls.convert_intertables_to_v2(filepath, logger)
            elif filepath.endswith('.npy'):
                intertable = np.load(filepath)
                if '_MISSING_' in filepath:
                    filepath = filepath.replace('_MISSING_', '_M_')
                    logger.info('Filename will change to {}'.format(util.files.file_name(filepath)))
                    filename_changed = True
                if filepath.endswith('_nn.npy'):
                    # convert grib nn
                    xs = intertable[0].astype(int, copy=False)
                    ys = intertable[1].astype(int, copy=False)
                    indexes = intertable[2].astype(int, copy=False)
                    intertable = np.asarray([xs, ys, indexes])
                    np.save(filepath, intertable)
                    logger.info('Converted: {}'.format(util.files.file_name(filepath)))
                elif filepath.endswith('_inv.npy'):
                    # convert grib invdist
                    try:
                        indexes = intertable['indexes']
                    except IndexError:
                        # in version 1 indexes were stored as float
                        xs = intertable[0].astype(int, copy=False)
                        ys = intertable[1].astype(int, copy=False)
                        idxs1 = intertable[2].astype(int, copy=False)
                        idxs2 = intertable[3].astype(int, copy=False)
                        idxs3 = intertable[4].astype(int, copy=False)
                        idxs4 = intertable[5].astype(int, copy=False)
                        coeffs1 = intertable[6]
                        coeffs2 = intertable[7]
                        coeffs3 = intertable[8]
                        coeffs4 = intertable[9]
                        indexes = np.asarray([xs, ys, idxs1, idxs2, idxs3, idxs4])
                        coeffs = np.asarray([coeffs1, coeffs2, coeffs3, coeffs4, np.zeros(coeffs1.shape), np.zeros(coeffs1.shape)])
                        intertable = np.rec.fromarrays((indexes, coeffs), names=('indexes', 'coeffs'))
                        np.save(filepath, intertable)
                        logger.info('Converted: {}'.format(util.files.file_name(filepath)))
                    else:
                        # already in new format
                        pass
                elif filename_changed:
                    # For scipy intertables, we just need to save intertable with a different filename (GRID ID changed)
                    np.save(filepath, intertable)
        logger.detach_config_logger()
