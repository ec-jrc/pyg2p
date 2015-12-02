from gribpcraster.application.readers.PCRasterReader import PCRasterReader
from util.logger import Logger


class LatLongBuffer:

    def __init__(self, latMapFile, longMapFile):
        self._latMap = latMapFile
        self._longMap = longMapFile
        self._logger = Logger.get_logger()

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