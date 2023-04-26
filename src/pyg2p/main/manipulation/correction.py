import logging

import numexpr as ne
import numpy as np
from numpy import ma
from pyg2p import Loggable

from pyg2p.main.interpolation import Interpolator
from pyg2p.main.interpolation.latlong import Dem
from pyg2p.main.readers.grib import GRIBReader

from pyg2p.main.config import GeopotentialsConfiguration
import pyg2p.util.numeric
from netCDF4 import default_fillvals

from ..interpolation.scipy_interpolation_lib import DEBUG_BILINEAR_INTERPOLATION, \
                                        DEBUG_MIN_LAT, DEBUG_MIN_LON, DEBUG_MAX_LAT, DEBUG_MAX_LON

class Corrector(Loggable):

    instances = {}

    def __repr__(self):
        return f'Corrector<{self.grid_id} {self.geo_file}>'

    @classmethod
    def get_instance(cls, ctx, grid_id):
        geo_file_ = ctx.geo_file(grid_id)
        dem_map = ctx.get('correction.demMap')
        key = f'{grid_id}{dem_map}'
        if key in cls.instances:
            return cls.instances[key]
        else:
            instance = Corrector(ctx, grid_id, geo_file_)
            cls.instances[key] = instance
            return instance

    def __init__(self, ctx, grid_id, geo_file):
        super().__init__()
        self.geo_file = geo_file
        self.grid_id = grid_id
        dem_map = ctx.get('correction.demMap')
        self._dem_missing_value, self._dem_values = self._read_dem(dem_map)
        self._formula = ctx.get('correction.formula')
        self._gem_formula = ctx.get('correction.gemFormula')
        self._numexpr_eval = f'where((dem!=dem_mv) & (p!=mv) & (gem!=gem_mv), {self._formula}, mv)'
        self._numexpr_eval_gem = f'where(z != mv, {self._gem_formula}, mv)'

        log_message = f"""
        Correction
        Reading dem: {dem_map}
        geopotential: {geo_file}
        formula: {self._formula.replace('gem', self._gem_formula)}
        """
        self._log(log_message, 'INFO')

        self._gem_missing_value, self._gem_values = self._read_geo(geo_file, ctx)

    def correct(self, values):
        with np.errstate(over='ignore'):
            # variables below are used by numexpr evaluation namespace
            if DEBUG_BILINEAR_INTERPOLATION:
                if self._dem_values.shape==(3600,7200):
                    # Global_3arcmin DEBUG
                    dem = self._dem_values[1800-int(DEBUG_MAX_LAT*20):1800-int(DEBUG_MIN_LAT*20), 3600+int(DEBUG_MIN_LON*20):3600+int(DEBUG_MAX_LON*20)]
                else:
                    # European_1arcmin DEBUG, not supported for correction debug yet
                    # selection_lats = np.logical_and(self._target_coords.lats[:,0]>=DEBUG_MIN_LAT,self._target_coords.lats[:,0]<=DEBUG_MAX_LAT)
                    # selection_lons = np.logical_and(self._target_coords.lons[0,:]>=DEBUG_MIN_LON,self._target_coords.lons[0,:]<=DEBUG_MAX_LON)
                    # dem = self._dem_values[selection_lats,:][:,selection_lons]
                    assert(False)
            else:
                dem = self._dem_values
            p = values
            gem = self._gem_values
            dem_mv = self._dem_missing_value
            gem_mv = self._gem_missing_value
            mv = default_fillvals[values.dtype.str[1:]] # take missing values from the default netCDF fillvals values
            values = ne.evaluate(self._numexpr_eval)
            # mask out values (here is already output values with destination shape)
            values = ma.masked_where(pyg2p.util.numeric.get_masks(p), values)
        return values

    def _read_geo(self, grib_file, ctx):
        is_grib_interpolation = ctx.is_with_grib_interpolation
        reader = GRIBReader(grib_file)
        kwargs = {'shortName': GeopotentialsConfiguration.short_names}
        geopotential_gribs = reader.select_messages(**kwargs)
        missing = geopotential_gribs.missing_value
        values = geopotential_gribs.first_resolution_values()[geopotential_gribs.first_step_range]
        aux_g, aux_v, aux_g2, aux_v2 = reader.get_gids_for_grib_intertable()
        interpolator = Interpolator(ctx, missing)
        interpolator.aux_for_intertable_generation(aux_g, aux_v, aux_g2, aux_v2)

        # get temp from geopotential. will be gem in the formula
        # variables below are used by numexpr evaluation namespace: DO NOT DELETE!
        mv = missing
        z = values
        ne.evaluate(self._numexpr_eval_gem, out=values)

        if is_grib_interpolation:
            values_resampled = interpolator.interpolate_grib(values, -1, self.grid_id)
        else:
            # FOR GEOPOTENTIALS, SOME GRIBS COME WITHOUT LAT/LON GRIDS!
            lats, lons = geopotential_gribs.latlons
            values_resampled = interpolator.interpolate_scipy(lats, lons, values, self.grid_id, geopotential_gribs.grid_details)
        reader.close()
        return missing, values_resampled

    @staticmethod
    def _read_dem(dem_map):
        dem = Dem(dem_map)
        return dem.mv, dem.values
