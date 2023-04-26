import logging

from pyg2p import Loggable
from pyg2p.exceptions import ApplicationException, INVALID_INTERPOL_METHOD
from pyg2p.main.readers.pcr import PCRasterReader
from pyg2p.main.readers.netcdf import NetCDFReader
from netCDF4 import default_fillvals

class LatLong(Loggable):

    def __init__(self, lat_map, long_map):
        super().__init__()
        self._lat_map = lat_map
        self._long_map = long_map
        self._logger = logging.getLogger()
        
        if self._lat_map.endswith('.nc'):
            if (self._lat_map!=self._long_map):
                raise ApplicationException.get_exc(INVALID_INTERPOL_METHOD, 
                    f"lat map and long map should coincide when using netCDF target map, used {self._lat_map} amd {self._long_map}")

            reader = NetCDFReader(self._lat_map)
            self.lats, self.lons = reader.get_lat_lon_values()
            self.mv = default_fillvals[self.lats.dtype.str[1:]] # take missing values from the default netCDF fillvals values

            self._id = reader.identifier()
        else:
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
        if self._dem_map.endswith('.nc'):
            reader = NetCDFReader(self._dem_map)
        else:
            reader = PCRasterReader(self._dem_map)
        self.mv = reader.mv
        self.values = reader.values
