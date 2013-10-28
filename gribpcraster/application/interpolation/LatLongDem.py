from gribpcraster.application.readers.PCRasterReader import PCRasterReader
from util.logger.Logger import Logger

__author__ = "nappodo"
__date__ = "$Feb 20, 2013 4:11:13 PM$"

PROJ4_STRING_EFAS = {'proj':'laea', 'lat_0':48.0, 'lon_0':9.0 ,'x_0':0.0 ,'y_0':0.0 ,'datum':'WGS84' ,'a':6378388 ,'b':6378388}
import gribpcraster.application.ExecutionContext as ex

class LatLongBuffer:

    def __init__(self, latMapFile, longMapFile):
        self._latMap = latMapFile
        self._longMap = longMapFile
        import gribpcraster.application.ExecutionContext as ex
        #ex.global_logger_level
        self._logger = Logger('LatLongMapsBuffer',loggingLevel=ex.global_logger_level)

        self.area_extent = (-1700000, -1350000, 1700000, 2700000)

        self._log('Reading latitudes values from: ' + str(self._latMap))
        reader = PCRasterReader(self._latMap)
        self._missing_value = reader.getMissingValue()
        self._latMapValues = reader.getValues()
        reader.close()

        self._log('Reading longitudes values from: ' + str(self._longMap))
        reader2 = PCRasterReader(self._longMap)
        self._lonMapValues = reader2.getValues()
        reader2.close()

        self._id = reader.getId()+'_'+reader2.getId()

    def getId(self):
        return self._id

    def getLat(self):
        return self._latMapValues

    def getLong(self):
        return self._lonMapValues

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def getMissingValue(self):
        return self._missing_value


class DemBuffer(object):
    _demCache = {}

    def __init__(self, demMapFile):
        self._demMap = demMapFile
        self._logger = Logger('DemMapBuffer')
        self._log('Reading altitude values from: ' + demMapFile, 'INFO')
        reader = PCRasterReader(self._demMap)
        self._missing_value = reader.getMissingValue()
        self._demMapValues = reader.getValues()
        reader.close()

    def getDem(self):
        return self._demMapValues

    def getMissingValue(self):
        return self._missing_value

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)