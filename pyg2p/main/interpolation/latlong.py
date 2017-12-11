from pyg2p.main.readers.pcr import PCRasterReader
from pyg2p.util.logger import Logger


class LatLong(object):

    def __init__(self, lat_map, long_map):
        self._lat_map = lat_map
        self._long_map = long_map
        self._logger = Logger.get_logger()

        self._log('Reading latitudes values from: {}'.format(self._lat_map))
        reader = PCRasterReader(self._lat_map)
        self._missing_value = reader.missing_value
        self._latMapValues = reader.values

        self._log('Reading longitudes values from: {}'.format(self._long_map))
        reader2 = PCRasterReader(self._long_map)
        self._lonMapValues = reader2.values

        self._id = '{}_{}'.format(reader.identifier(), reader2.identifier())

    @property
    def identifier(self):
        return self._id

    @property
    def lats(self):
        return self._latMapValues

    @property
    def longs(self):
        return self._lonMapValues

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    @property
    def missing_value(self):
        return self._missing_value


class DemBuffer(object):
    _demCache = {}

    def __init__(self, dem_map):
        self._dem_map = dem_map
        self._logger = Logger.get_logger()
        self._log('Reading altitude values from: {}'.format(dem_map))
        reader = PCRasterReader(self._dem_map)
        self._missing_value = reader.missing_value
        self._values = reader.values

    @property
    def values(self):
        return self._values

    @property
    def missing_value(self):
        return self._missing_value

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)
