from main.interpolation.latlong import DemBuffer
from main.readers.grib import GRIBReader
from main.interpolation import Interpolator
import numpy as np
import numexpr as ne
from main.config import GeopotentialsConfiguration
from util.logger import Logger


class Corrector(object):

    INSTANCES = {}

    @classmethod
    def get_instance(cls, ctx, grid_id):
        geo_file_ = ctx.geo_file(grid_id)
        dem_map = ctx.get('correction.demMap')
        key = '{}{}'.format(geo_file_, dem_map)
        if key in cls.INSTANCES:
            return cls.INSTANCES[key]
        else:
            instance = Corrector(ctx, geo_file_)
            cls.INSTANCES[key] = instance
            return instance

    def __init__(self, ctx, geo_file_):
        self._logger = Logger.get_logger()
        dem_map = ctx.get('correction.demMap')
        self._dem_missing_value, self._dem_values = self._read_dem(dem_map)
        self._formula = ctx.get('correction.formula')
        self._gem_formula = ctx.get('correction.gemFormula')
        self._numexpr_eval = 'where((dem!=mv) & (p!=mv) & (gem!=mv), {}, mv)'.format(self._formula)
        self._numexpr_eval_gem = 'where(z != mv, {}, mv)'.format(self._gem_formula)
        log_message = """
        Correction
        Reading dem:{}
        geopotential:{}
        formula: {}
        """.format(dem_map, geo_file_, self._formula.replace('gem', self._gem_formula))
        self._log(log_message, 'INFO')
        interpolator = Interpolator(ctx)

        self._gem_missing_value, self._gem_values = self._read_geo(geo_file_, interpolator, ctx.interpolate_with_grib)

    def correct(self, values):
        with np.errstate(over='ignore'):
            # variables below are used by numexpr evaluation namespace
            dem = self._dem_values
            p = values
            gem = self._gem_values
            mv = self._dem_missing_value
            ne.evaluate(self._numexpr_eval, out=values)
        return values

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def _read_geo(self, grib_file, interpolator, is_grib_interpolation):
        # import ipdb
        # ipdb.set_trace()
        reader = GRIBReader(grib_file)
        kwargs = {'shortName': GeopotentialsConfiguration.short_names, 'startStep': 0, 'endStep': 0}
        messages, short_name = reader.select_messages(**kwargs)
        aux_g, aux_v, aux_g2, aux_v2 = reader.get_gids_for_grib_intertable()
        interpolator.aux_for_intertable_generation(aux_g, aux_v, aux_g2, aux_v2)

        missing = messages.missing_value
        values = messages.first_resolution_values()[messages.first_step_range]
        # get temp from geopotential. will be gem in the formula
        # variables below are used by numexpr evaluation namespace
        mv = missing
        z = values
        ne.evaluate(self._numexpr_eval_gem, out=values)

        if is_grib_interpolation:
            values_resampled, intertable_was_used = interpolator.interpolate_grib(values, -1, messages.grid_id)
        else:
            # FOR GEOPOTENTIALS, SOME GRIBS COME WITHOUT LAT/LON GRIDS!
            # lat, lon = messages.getLatLons()
            # interpolation of geopotentials always with intertable!
            # lat and lons grib are None here and interpolation should find an intertable
            lats, lons = messages.latlons
            values_resampled = interpolator.interpolate_scipy(lats, lons, values, messages.grid_id, messages.grid_details)
        reader.close()
        return missing, values_resampled

    @staticmethod
    def _read_dem(dem_map):
        dem = DemBuffer(dem_map)
        return dem.missing_value, dem.values
