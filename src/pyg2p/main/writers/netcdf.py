import time

import numpy as np
from netCDF4 import Dataset

from pyg2p.main.readers.pcr import PCRasterReader
from pyg2p.main.writers import Writer
from pyg2p.exceptions import ApplicationException, INVALID_INTERPOL_METHOD
from pyg2p.main.readers.netcdf import NetCDFReader

from pyg2p.main.interpolation.scipy_interpolation_lib import DEBUG_BILINEAR_INTERPOLATION, \
                                        DEBUG_MIN_LAT, DEBUG_MIN_LON, DEBUG_MAX_LAT, DEBUG_MAX_LON

class NetCDFWriter(Writer):
    FORMAT = 'netcdf'
    esri_pe_string = 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["Degree",0.0174532925199433]]'

    def __init__(self, *args):
        super().__init__(*args)
        self.nf = None
        self.filepath = None
        lats_map, lons_map = args[1], args[2]
        if self._clone_map.endswith('.nc'):
            area = NetCDFReader(self._clone_map)
            self.area = area.values
        else:
            area = PCRasterReader(self._clone_map)
            self.area = area.values

        if lats_map.endswith('.nc'):
            if (lats_map!=lons_map):
                raise ApplicationException.get_exc(INVALID_INTERPOL_METHOD, 
                    f"lat map and long map should coincide when using netCDF target map, used {lats_map} amd {lons_map}")

            self.lats_map = NetCDFReader(lats_map)
            self.coordinates_mv = self.lats_map.mv
            self.lats, self.lons = self.lats_map.get_lat_lon_values()
            self.lats[self.lats == self.coordinates_mv] = np.nan
            self.lons[self.lons == self.coordinates_mv] = np.nan
        else:
            self.lats_map = PCRasterReader(lats_map)
            self.coordinates_mv = self.lats_map.mv
            self.lats = self.lats_map.values
            self.lons = PCRasterReader(lons_map).values
            self.lats[self.lats == self.coordinates_mv] = np.nan
            self.lons[self.lons == self.coordinates_mv] = np.nan

    def init_dataset(self, out_filename):
        self.nf = Dataset(out_filename, 'w', format='NETCDF4_CLASSIC')
        self.filepath = out_filename
        time_created = time.ctime(time.time())
        self.nf.history = f'Created {time_created}'
        self.nf.Conventions = 'CF-1.6'
        self.nf.Source_Software = 'pyg2p 3'
        self.nf.source = 'ECMWF'
        self.nf.reference = 'ECMWF'

        # Dimensions
        self.nf.createDimension('lon', self.area.shape[1])
        self.nf.createDimension('lat', self.area.shape[0])
        self.nf.createDimension('time', None)

    def write(self, values, time_values, **varargs):
        # Variables
        longitude = self.nf.createVariable('lon', 'f4', ('lon',), complevel=4, zlib=True)
        longitude.standard_name = 'Longitude'
        longitude.long_name = 'Longitude coordinate'
        longitude.units = 'degrees_east'

        latitude = self.nf.createVariable('lat', 'f4', ('lat',), complevel=4, zlib=True)
        latitude.standard_name = 'Latitude'
        latitude.long_name = 'Latitude coordinate'
        latitude.units = 'degrees_north'

        time_nc = self.nf.createVariable('time', 'f', ('time',), complevel=4, zlib=True)
        time_nc.standard_name = 'time'
        time_nc.units = f'hours since {varargs.get("data_date")}'
        time_nc.frequency = '1'
        time_nc.calendar = 'proleptic_gregorian'
        time_nc[:] = time_values

        values_nc = self.nf.createVariable(varargs.get('prefix', ''), 'f8',
                                           ('time', 'lat', 'lon'), zlib=True, complevel=4, fill_value=-9999,
                                           )
        values_nc.missing_value=-9999
        values_nc.coordinates = 'lon lat'
        values_nc.esri_pe_string = self.esri_pe_string
        values_nc.standard_name = varargs.get('prefix', '')
        values_nc.long_name = varargs.get('var_long_name', '')
        values_nc.units = varargs.get('unit', '')
        for t in range(len(time_values)):
            if DEBUG_BILINEAR_INTERPOLATION:
                values_nc[t, 1800-(DEBUG_MAX_LAT*20):1800-(DEBUG_MIN_LAT*20), 3600+(DEBUG_MIN_LON*20):3600+(DEBUG_MAX_LON*20)] = values[t, :, :]
            else:
                values_nc[t, :, :] = values[t,:,:]
        longitude[:] = self.lons[1,:]
        latitude[:] = self.lats[:,1]

    def close(self):
        self.nf.close()
        self._log(f'{self.filepath} written!', 'INFO')
