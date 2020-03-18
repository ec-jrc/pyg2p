import logging

from pyg2p import Loggable
from pyg2p.main.readers.pcr import PCRasterReader


class LatLong(Loggable):

    def __init__(self, lat_map, long_map):
        super().__init__()
        self._lat_map = lat_map
        self._long_map = long_map
        self._logger = logging.getLogger()

        self._log(f'Reading latitudes values from: {self._lat_map}')
        reader = PCRasterReader(self._lat_map)
        self._missing_value = reader.missing_value
        self._latMapValues = reader.values

        self._log(f'Reading longitudes values from: {self._long_map}')
        reader2 = PCRasterReader(self._long_map)
        self._lonMapValues = reader2.values

        self._id = f'{reader.identifier()}_{reader2.identifier()}'
        reader.close()
        reader2.close()

    @property
    def identifier(self):
        return self._id

    @property
    def lats(self):
        return self._latMapValues

    @property
    def longs(self):
        return self._lonMapValues

    @property
    def missing_value(self):
        return self._missing_value


class DemBuffer(Loggable):

    def __init__(self, dem_map):
        super().__init__()
        self._dem_map = dem_map
        self._logger = logging.getLogger()
        self._log(f'Reading altitude values from: {dem_map}')
        reader = PCRasterReader(self._dem_map)
        self._missing_value = reader.missing_value
        self._values = reader.values

    @property
    def values(self):
        return self._values

    @property
    def missing_value(self):
        return self._missing_value
