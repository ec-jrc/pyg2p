import time

import numpy as np
from netCDF4 import Dataset

from pyg2p.main.readers.pcr import PCRasterReader
from pyg2p.main.writers import Writer


class NetCDFWriter(Writer):
    FORMAT = 'netcdf'
    esri_pe_string = 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["Degree",0.0174532925199433]]'

    def __init__(self, *args):
        super(NetCDFWriter, self).__init__(*args)
        self.nf = None
        self.filepath = None
        lats_map, lons_map = args[1], args[2]
        area = PCRasterReader(self._clone_map)
        self.area = area.values
        self.lats_map = PCRasterReader(lats_map)
        self.coordinates_mv = self.lats_map.missing_value
        self.lats = self.lats_map.values
        self.lons = PCRasterReader(lons_map).values
        self.lats[self.lats == self.coordinates_mv] = np.nan
        self.lons[self.lons == self.coordinates_mv] = np.nan

    def init_dataset(self, out_filename):
        self.nf = Dataset(out_filename, 'w', format='NETCDF4')
        self.filepath = out_filename
        time_created = time.ctime(time.time())
        self.nf.history = 'Created {}'.format(time_created)
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
        longitude = self.nf.createVariable('lon', 'f4', ('lat', 'lon'))
        longitude.standard_name = 'longitude'
        longitude.long_name = 'longitude coordinate'
        longitude.units = 'degrees_east'

        latitude = self.nf.createVariable('lat', 'f4', ('lat', 'lon'))
        latitude.standard_name = 'latitude'
        latitude.long_name = 'latitude coordinate'
        latitude.units = 'degrees_north'

        time_nc = self.nf.createVariable('time', 'f', ('time',))
        time_nc.standard_name = 'time'
        time_nc.units = 'hours since {}'.format(varargs.get('data_date'))
        time_nc.calendar = 'proleptic_gregorian'
        time_nc[:] = time_values

        values_nc = self.nf.createVariable(varargs.get('prefix', ''), 'f8',
                                           ('time', 'lat', 'lon'), zlib=False,
                                           )
        values_nc.coordinates = 'lon lat'
        values_nc.esri_pe_string = self.esri_pe_string
        values_nc.standard_name = varargs.get('prefix', '')
        values_nc.long_name = varargs.get('var_long_name', '')
        values_nc.units = varargs.get('unit', '')
        values_nc[:, :] = values
        longitude[:] = self.lons
        latitude[:] = self.lats

    def close(self):
        self.nf.close()
        self._log('{} written!'.format(self.filepath), 'INFO')
