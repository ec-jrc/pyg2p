import logging

from osgeo import gdal
from osgeo.gdalconst import GA_ReadOnly
from pyg2p import Loggable


class PCRasterReader(Loggable):

    FORMAT = 'PCRaster'

    def __init__(self, pcr_map):
        super().__init__()
        self._log('Reading {}'.format(pcr_map))

        self._driver = gdal.GetDriverByName(self.FORMAT)
        i = self._driver.Register()
        self._dataset = gdal.Open(pcr_map.encode('utf-8'), GA_ReadOnly)
        self._getTransform = self._dataset.GetGeoTransform()
        self._cols = self._dataset.RasterXSize
        self._rows = self._dataset.RasterYSize
        self._origX = self._getTransform[0]
        self._origY = self._getTransform[3]
        self._pxlW = self._getTransform[1]
        self._pxlH = self._getTransform[5]

        self._band = self._dataset.GetRasterBand(1)
        self._min = self._band.GetMinimum()
        self._max = self._band.GetMaximum()
        self._mv = self._band.GetNoDataValue()


    @property
    def values(self):
        data = self._band.ReadAsArray(0, 0, self._cols, self._rows)
        self.close()
        return data

    @property
    def missing_value(self):
        return self._mv

    def close(self):
        self._band = None
        self._dataset = None

    def identifier(self):
        return '{}_{}_{}_{}_{:.2f}_{:.2f}'.format(int(self._origX), int(self._origY),
                                                  int(self._pxlW), int(self._pxlH),
                                                  self._min, self._max)

