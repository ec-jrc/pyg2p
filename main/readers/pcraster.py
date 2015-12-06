import gdal
from gdalconst import *
from util.logger import Logger


class PCRasterReader(object):

    FORMAT = 'PCRaster'

    def __init__(self, pcrasterMap):
        self._logger = Logger.get_logger()
        self._log('Reading ' + pcrasterMap)

        self._driver = gdal.GetDriverByName(self.FORMAT)
        i = self._driver.Register()
        self._dataset = gdal.Open(pcrasterMap.encode('utf-8'), GA_ReadOnly)
        self._getTransform = self._dataset.GetGeoTransform()
        self._cols = self._dataset.RasterXSize
        self._rows = self._dataset.RasterYSize
        self._origX = self._getTransform[0]
        self._origY = self._getTransform[3]
        self._pxlW = self._getTransform[1]
        self._pxlH = self._getTransform[5]
        self._area_extent = (self._origX, self._origX + (self._pxlW * self._cols), self._origY - (self._pxlH * self._rows), self._origY)

        self._band = self._dataset.GetRasterBand(1)
        self._min = self._band.GetMinimum()
        self._max = self._band.GetMaximum()

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def getValues(self):
        data = self._band.ReadAsArray(0, 0, self._cols, self._rows)
        return data

    @property
    def missing_value(self):
        return self._band.GetNoDataValue()

    def close(self):
        self._band = None
        self._dataset = None

    def getXYOrigins(self):
        return self._origX, self._origY

    def getAreaExtent(self):
        return self._area_extent

    def getId(self):
        return "%d_%d_%d_%d_%.2f_%.2f" % (self._origX, self._origY, self._pxlW, self._pxlH, self._min, self._max)

