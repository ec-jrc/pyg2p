from pathlib import Path

from osgeo import gdal
from osgeo.gdalconst import GA_ReadOnly

from pyg2p import Loggable


class PCRasterReader(Loggable):

    def __init__(self, pcr_map):
        super().__init__()
        self._log(f'Reading {pcr_map}')
        pcr_map = pcr_map.as_posix() if isinstance(pcr_map, Path) else pcr_map
        self._driver = gdal.GetDriverByName('PCRaster')
        _ = self._driver.Register()
        self._dataset = gdal.Open(pcr_map.encode('utf-8'), GA_ReadOnly)
        self._geo_transform = self._dataset.GetGeoTransform()
        self._cols = self._dataset.RasterXSize
        self._rows = self._dataset.RasterYSize
        self._origX = self._geo_transform[0]
        self._origY = self._geo_transform[3]
        self._pxlW = self._geo_transform[1]
        self._pxlH = self._geo_transform[5]

        self._band = self._dataset.GetRasterBand(1)
        self.min = self._band.GetMinimum()
        self.max = self._band.GetMaximum()
        self.mv = self._band.GetNoDataValue()

    @property
    def values(self):
        data = self._band.ReadAsArray(0, 0, self._cols, self._rows)
        self.close()
        return data

    def close(self):
        self._band = None
        self._dataset = None

    def identifier(self):
        return f'{int(self._origX)}_{int(self._origY)}_{int(self._pxlW)}_{int(self._pxlH)}_{self.min:.2f}_{self.max:.2f}'
