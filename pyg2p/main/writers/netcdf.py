import time

from netCDF4 import Dataset
from netCDF4 import num2date, date2num

from pyg2p.main.readers.pcraster import PCRasterReader
from pyg2p.util.logger import Logger
from pyg2p.main.writers import Writer


class NetCDFWriter(Writer):
    FORMAT = 'netCDF'

    def __init__(self, clone_map):
        self.nf = None
        self._clone_map = clone_map
        self._logger = Logger.get_logger()
        self.area = PCRasterReader(clone_map).values

    def init_dataset(self, out_filename):
        xcoord = 'lon'
        ycoord = 'lat'
        digit = 2
        self.nf = Dataset(out_filename, 'w', format='NETCDF4_CLASSIC')
        import time
        time_created = time.ctime(time.time())
        self.nf.history = 'Created {}'.format(time_created)
        self.nf.Conventions = 'CF-1.6'
        self.nf.Source_Software = 'Python netCDF4'
        self.nf.source = 'ECMWF REFORECAST'
        self.nf.reference = 'ECMWF'
        # Dimension
        lon = self.nf .createDimension(xcoord, self.area.shape[1])
        lat = self.nf .createDimension(ycoord, self.area.shape[0])
        time = self.nf .createDimension('time', None)

    def write(self, output_map_name, values):
        pass