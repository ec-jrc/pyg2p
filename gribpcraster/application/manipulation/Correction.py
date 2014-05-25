from gribpcraster.application.readers.GRIBReader import GRIBReader
from gribpcraster.application.readers.PCRasterReader import PCRasterReader
from gribpcraster.application.interpolation.Interpolation import Interpolator
from util.logger.Logger import Logger
import numpy as np
import numexpr as ne
import util.configuration.geopotentials as geop
import gribpcraster.application.ExecutionContext as ex
__author__ = 'dominik'


class Corrector(object):

    LOADED_GEOMS = []
    INSTANCES = {}

    @classmethod
    def getInstance(cls, executionContext, geo_file_):
        if geo_file_ in Corrector.LOADED_GEOMS:
            return Corrector.INSTANCES[geo_file_]
        else:

            instance = Corrector(executionContext, geo_file_)
            Corrector.INSTANCES[geo_file_]=instance
            Corrector.LOADED_GEOMS.append(geo_file_)
            return instance

    def __init__(self, executionContext, geo_file_):
        self._logger = Logger('Corrector', loggingLevel=executionContext.get('logger.level'))
        demMap = executionContext.get('correction.demMap')
        self._dem_missing_value, self._dem_values = _readDem(demMap)
        self._formula = executionContext.get('correction.formula')
        self._gem_formula = executionContext.get('correction.gemFormula')
        # self._f = np.vectorize(eval('lambda p,dem,gem,mv:' + self._formula + ' if dem!=mv and p!=mv and gem!=mv else mv'))
        self._numexpr_eval = 'where((dem!=mv)&(p!=mv)&(gem!=mv),' + self._formula + ', mv)'
        # self._fgem = np.vectorize(eval('lambda z,mv:'+self._gem_formula+' if z!=mv else mv'))
        self._numexpr_eval_gem = 'where(z!=mv,' + self._gem_formula + ', mv)'
        self._log('Reading dem:%s, geopotential:%s for correction (using: %s)'% (demMap,geo_file_,self._formula))
        self._log('Reading dem values %s)' % geo_file_)

        interpolator = Interpolator(executionContext)
        self._log('Reading geopotential values (with interpolation) %s)' % geo_file_)

        self._gem_missing_value, self._gem_values = self._readGeopotential(geo_file_, interpolator, executionContext.interpolate_with_grib())

    def correct(self, values):

        self._log('Correcting using %s, ignoring mv = %.2e)' % (self._formula, self._dem_missing_value))
        mvarray = np.empty(self._dem_values.shape)
        # mvarray[:] = self._dem_missing_value
        mvarray.fill(self._dem_missing_value)
        with np.errstate(over='ignore'):
            # variables below are used by numexpr evaluation namespace
            dem = self._dem_values
            p = values
            gem = self._gem_values
            mv = self._dem_missing_value
            values_corrected = ne.evaluate(self._numexpr_eval)

        return values_corrected

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def _readGeopotential(self, grib_file, interpolator, is_grib_interpolation):

        self._log('Reading %s for correction using one of %s)' % (grib_file, str(geop.SHORT_NAMES)))
        reader = GRIBReader(grib_file)
        kwargs = {'shortName': geop.SHORT_NAMES}
        messages, shortName = reader.getSelectedMessages(**kwargs)
        reader.close()
        missing = messages.getMissingValue()
        values = messages.getValuesOfFirstOrSingleRes()[messages.first_step_range]
        #get temp from geopotential. will be gem in the formula
        # variables below are used by numexpr evaluation namespace
        mv = missing
        z = values
        values_corrected = ne.evaluate(self._numexpr_eval_gem)

        if is_grib_interpolation:
            values_resampled, intertable_was_used = interpolator.interpolate_grib(values_corrected, -1, messages.getGridId())
        else:
            #FOR GEOPOTENTIALS, SOME GRIBS COME WITHOUT LAT/LON GRIDS!
            #lat, lon = messages.getLatLons()
            #interpolation of geopotentials always with intertable!
            #lat and lons grib are None here and interpolation should find an intertable
            values_resampled = interpolator.interpolate_with_scipy(None, None, values,messages.getGridId())

        return missing, values_resampled


def _readDem(demMap):
    reader = PCRasterReader(demMap)
    values = reader.getValues()
    missing = reader.getMissingValue()
    reader.close()
    return missing, values