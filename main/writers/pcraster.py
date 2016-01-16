import gdal
import numpy.ma as ma
from util.logger import Logger


class PCRasterWriter:
    FORMAT = 'PCRaster'

    def __init__(self, clone_map):
        self._clone_map = clone_map
        self._logger = Logger.get_logger()
        self._log("Set PCRaster clone for writing maps: " + self._clone_map)
        # =============================================================================
        # Create a MEM clone of the source file.
        # =============================================================================

        self._src_drv = gdal.GetDriverByName(self.FORMAT)
        self._src_drv.Register()
        self._src_ds = gdal.Open(self._clone_map.encode('utf-8'))
        self._src_band = self._src_ds.GetRasterBand(1)

        self._mem_ds = gdal.GetDriverByName('MEM').CreateCopy('mem', self._src_ds)

        # Producing mask array
        cols = self._src_ds.RasterXSize
        rows = self._src_ds.RasterYSize
        rs = self._src_band.ReadAsArray(0, 0, cols, rows)
        mv = self._src_band.GetNoDataValue()
        rs = ma.masked_values(rs, mv)
        self._mask = ma.getmask(rs)

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def write(self, output_map_name, values, mv=None):
        drv = gdal.GetDriverByName(self.FORMAT)
        masked_values = self._mask_values(values, mv)
        n = ma.count_masked(masked_values)
        self._mem_ds.GetRasterBand(1).SetNoDataValue(mv)
        self._mem_ds.GetRasterBand(1).WriteArray(masked_values)
        out_ds = drv.CreateCopy(output_map_name.encode('utf-8'), self._mem_ds)
        self._log('%s written!' % output_map_name, 'INFO')
        out_ds = None

    def _mask_values(self, values, mv):
        masked = ma.masked_where(self._mask == True, values, copy=False)
        masked = ma.filled(masked, self._src_band.GetNoDataValue())
        return masked

    def close(self):
        self._mem_ds = None
        self._src_ds = None
        self._src_band = None
