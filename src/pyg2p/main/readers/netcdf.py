from pathlib import Path

import numpy as np

from pyg2p import Loggable
import netCDF4 as nc
from netCDF4 import Dataset 
import warnings

class NetCDFReader(Loggable):

    def __init__(self, nc_map):
        super().__init__()
        self._log(f'Reading {nc_map}')
        nc_map = nc_map.as_posix() if isinstance(nc_map, Path) else nc_map
        self._dataset = Dataset(nc_map)
        self.var_name = self.find_main_var(nc_map)

        self._rows, self._cols = self._dataset.variables[self.var_name].shape  # just use shape to know rows and cols...
        if ('lon' in list(self._dataset.variables)):
            self.label_lat = 'lat'
            self.label_lon = 'lon'
        else:
            self.label_lat = 'y'
            self.label_lon = 'x'

        self._origX = self._dataset.variables[self.label_lon][:].min()
        self._origY = self._dataset.variables[self.label_lat][:].min()
        self._pxlW = self._dataset.variables[self.label_lon][1]-self._dataset.variables[self.label_lon][0]
        self._pxlH = self._dataset.variables[self.label_lat][1]-self._dataset.variables[self.label_lat][0]       
        self.lat_min = self._dataset.variables[self.label_lat][:].min()
        self.lon_min = self._dataset.variables[self.label_lon][:].min()
        self.lat_max = self._dataset.variables[self.label_lat][:].max()
        self.lon_max = self._dataset.variables[self.label_lon][:].max()
        self.mv = self._dataset.variables[self.var_name].missing_value

    def find_main_var(self, path):
        variable_names = [k for k in self._dataset.variables if len(self._dataset.variables[k].dimensions) >= 2]
        if len(variable_names) > 1:
            warnings.warn('More than one variable in dataset {}'.format(path), RuntimeWarning)
        elif len(variable_names) == 0:
            warnings.warn('Could not find a valid variable in dataset {}'.format(path), RuntimeWarning)
        else:
            var_name = variable_names[0]
        return var_name

    @property
    def values(self):
        data = self._dataset.variables[self.var_name][:].data
        return data
    
    def get_lat_lon_values(self):
        lats = np.reshape(self._dataset.variables[self.label_lat][:],(-1,1))*np.ones(self._dataset.variables[self.var_name].shape)
        lons = self._dataset.variables[self.label_lon][:]*np.ones(self._dataset.variables[self.var_name].shape)
        return lats.data, lons.data

    def get_lat_values(self):
        return self._dataset.variables[self.label_lat][:].data

    def get_lon_values(self):
        return self._dataset.variables[self.label_lon][:].data

    def close(self):
        self._dataset = None

    def identifier(self):
        latidentifier=f'{int(self._origX)}_{int(self._origY)}_{int(self._pxlW)}_{int(self._pxlH)}_{self.lat_min:.2f}_{self.lat_max:.2f}'
        lonidentifier=f'{int(self._origX)}_{int(self._origY)}_{int(self._pxlW)}_{int(self._pxlH)}_{self.lon_min:.2f}_{self.lon_max:.2f}'
        return f'{latidentifier}_{lonidentifier}'