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
        self.mv = reader.mv
        self.lats = reader.values

        self._log(f'Reading longitudes values from: {self._long_map}')
        reader2 = PCRasterReader(self._long_map)
        self.lons = reader2.values

        self._id = f'{reader.identifier()}_{reader2.identifier()}'
        reader.close()
        reader2.close()

    @property
    def identifier(self):
        return self._id


class Dem(Loggable):

    def __init__(self, dem_map):
        super().__init__()
        self._dem_map = dem_map
        self._log(f'Reading altitude values from: {dem_map}')
        reader = PCRasterReader(self._dem_map)
        self.mv = reader.mv
        self.values = reader.values
