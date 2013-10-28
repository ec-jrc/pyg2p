__author__ = 'dominik'

import abc
import gribpcraster.application.ExecutionContext as ex

class GridDetails(object):

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def getLatLons(self):
        return


    @abc.abstractmethod
    def getShape(self):
        return self._lats.shape

    @abc.abstractmethod
    def getGridType(self):
        return self._grid_type

    @abc.abstractmethod
    def getGridId(self):
        return self._grid_id

    @abc.abstractmethod
    def getNumberOfPointsAlongMeridian(self):
        return self._points_meridian

    @abc.abstractmethod
    def set_2nd_resolution(self, grid2nd, step_range_):
        return

    @abc.abstractmethod
    def get_2nd_resolution(self):
        return self._grid_details_2nd

    @abc.abstractmethod
    def get_change_res_step(self):
        return self._change_resolution_step

    @abc.abstractmethod
    def get_geo_keys(self):
        return self._geo_keys

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)