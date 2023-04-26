import time
import warnings

import numpy as np
from netCDF4 import Dataset, default_fillvals

from pyg2p.main.readers.pcr import PCRasterReader
from pyg2p.main.writers import Writer
from pyg2p.exceptions import ApplicationException, INVALID_INTERPOL_METHOD
from pyg2p.main.readers.netcdf import NetCDFReader
from netCDF4 import default_fillvals

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
            self.lats, self.lons = self.lats_map.get_lat_lon_values()
        else:
            self.lats_map = PCRasterReader(lats_map)
            coordinates_mv = self.lats_map.mv
            self.lats = self.lats_map.values
            self.lons = PCRasterReader(lons_map).values
            self.lats[self.lats == coordinates_mv] = np.nan
            self.lons[self.lons == coordinates_mv] = np.nan

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
        longitude = self.nf.createVariable('lon', 'f8', ('lon',), complevel=4, zlib=True)
        longitude.standard_name = 'Longitude'
        longitude.long_name = 'Longitude coordinate'
        longitude.units = 'degrees_east'

        latitude = self.nf.createVariable('lat', 'f8', ('lat',), complevel=4, zlib=True)
        latitude.standard_name = 'Latitude'
        latitude.long_name = 'Latitude coordinate'
        latitude.units = 'degrees_north'


        time_var_format = 'i4'
        steps_units_netcdf_name = {'s':'seconds', 'm':'minutes', 'h':'hours', '3h':'3h steps', '6h':'6h steps',
                                    '12h':'12h steps', 'D': 'days', 'M': 'months', 'Y': 'years', '10Y': '10Y steps', 
                                    '30Y':'30Y steps', 'C': 'centuries'}
        steps_units_conversion_time = {'s':1/3600, 'm':1/60, 'h':1, '3h':3, '6h':6,
                                    '12h':12, 'D': 24}
        
        grib_step_units=varargs.get("grib_step_units")
        if varargs.get('output_step_units', None) is not None:
            # force the destination step units
            output_step_units=varargs.get("output_step_units")
            if output_step_units in steps_units_netcdf_name: 
                if output_step_units!=grib_step_units:
                    # the time_values need to be converted here
                    # we can convert only up to daily step
                    if (output_step_units in steps_units_conversion_time) and \
                        (grib_step_units in steps_units_conversion_time): 
                        time_values = time_values*steps_units_conversion_time[grib_step_units]/steps_units_conversion_time[output_step_units]
                        if np.any(np.mod(time_values, 1) != 0):
                            time_var_format = 'f4'
                    else:
                        warnings.warn('Conversion from grib stepUnits {} to outputStepUnits: {} not allowed.\nConversion is supported only up to daily time steps. The output format will be "{}"'
                                    .format(grib_step_units, output_step_units,steps_units_netcdf_name[grib_step_units]), 
                                    RuntimeWarning)
                        output_step_units = grib_step_units
            else:
                warnings.warn('Invalid outputStepUnits: {}. Valid values are: {}\nUsing source step unit: {}'
                              .format(output_step_units,steps_units_netcdf_name,grib_step_units), 
                              RuntimeWarning)
                output_step_units = grib_step_units
        else:
            # ok, I use the source step units
            output_step_units=grib_step_units

        netcdf_steps_units = steps_units_netcdf_name[output_step_units]
        data_date=varargs.get("data_date")

        time_nc = self.nf.createVariable('time', time_var_format, ('time',), complevel=4, zlib=True)
        time_nc.standard_name = 'time'
        time_nc.units = f'{netcdf_steps_units} since {data_date}'
        time_nc.frequency = '1'
        time_nc.calendar = 'proleptic_gregorian'
        time_nc[:] = time_values

        value_format = varargs.get('value_format', 'f8')
        if value_format is None:
            value_format = 'f8'

        # test: use always default_fillvals as the missing value 
        missing_value_to_use = default_fillvals[value_format]
        
        values_nc = self.nf.createVariable(varargs.get('prefix', ''), value_format,
                                           ('time', 'lat', 'lon'), zlib=True, complevel=4, fill_value=missing_value_to_use,
                                           )
        values_nc.missing_value=missing_value_to_use
        values_nc.coordinates = 'lon lat'
        values_nc.esri_pe_string = self.esri_pe_string
        values_nc.standard_name = varargs.get('prefix', '')
        values_nc.long_name = varargs.get('var_long_name', '')
        values_nc.units = varargs.get('unit', '')
        values_nc.scale_factor = np.float64(varargs.get('scale_factor', '1.0'))
        values_nc.add_offset = np.float64(varargs.get('offset', '0.0'))
        if varargs.get('valid_min', None) is not None:
            values_nc.valid_min = (np.float64(varargs.get('valid_min', None)) - np.float64(varargs.get('offset', '0.0'))) / np.float64(varargs.get('scale_factor', '1.0'))
        if varargs.get('valid_max', None) is not None:            
            values_nc.valid_max = (np.float64(varargs.get('valid_max', None)) - np.float64(varargs.get('offset', '0.0'))) / np.float64(varargs.get('scale_factor', '1.0'))
        values_nc.set_auto_maskandscale(True)         

        # adjust missing values when scale_factor and offset are not 1.0 - 0.0 
        values[np.isnan(values)] = np.float64(missing_value_to_use) * np.float64(varargs.get('scale_factor', '1.0')) + np.float64(varargs.get('offset', '0.0'))
        
        for t in range(len(time_values)):
            if DEBUG_BILINEAR_INTERPOLATION:
                if self.lats.shape==(3600,7200):
                    # Global_3arcmin DEBUG
                    values_nc[t, 1800-int(DEBUG_MAX_LAT*20):1800-int(DEBUG_MIN_LAT*20), 3600+int(DEBUG_MIN_LON*20):3600+int(DEBUG_MAX_LON*20)] = values[t, :, :]
                else:
                    # European_1arcmin DEBUG
                    selection_lats = np.logical_and(self.lats[:,0]>=DEBUG_MIN_LAT,self.lats[:,0]<=DEBUG_MAX_LAT)
                    selection_lons = np.logical_and(self.lons[0,:]>=DEBUG_MIN_LON,self.lons[0,:]<=DEBUG_MAX_LON)
                    values_all=values_nc[t,:,:].data
                    values_all[np.ix_(selection_lats,selection_lons)] = values[t, :, :]
                    values_nc[t,:,:]=values_all[:,:]
            else:
                values_nc[t, :, :] = values[t,:,:]
        longitude[:] = self.lons[0,:]
        latitude[:] = self.lats[:,0]

    def close(self):
        self.nf.close()
        self._log(f'{self.filepath} written!', 'INFO')
