# Managed grid types:
# regular_gg, regular_ll
# reduced_ll, reduced_gg
# rotated_ll, rotated_gg

import gribapi
import numpy as np

from util.logger import Logger


class GribGridDetails(object):

    @staticmethod
    def _build_id(gid, grid_type):
        ni = 'MISSING' if gribapi.grib_is_missing(gid, 'Ni') else gribapi.grib_get(gid, 'Ni')
        nj = 'MISSING' if gribapi.grib_is_missing(gid, 'Nj') else gribapi.grib_get(gid, 'Nj')
        num_of_values = gribapi.grib_get(gid, 'numberOfValues')
        long_first = ('%.4f' % (gribapi.grib_get_double(gid, 'longitudeOfFirstGridPointInDegrees'),)).rstrip('0').rstrip('.')
        long_last = ('%.4f' % (gribapi.grib_get_double(gid, 'longitudeOfLastGridPointInDegrees'),)).rstrip('0').rstrip('.')
        grid_id = '{}${}${}${}${}${}'.format(long_first, long_last, ni, nj, num_of_values, grid_type)
        return grid_id

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def _getShape(self):
        nx = ny = 0
        if self._grid_type in ('regular_gg', 'regular_ll', 'rotated_ll', 'rotated_gg'):  # regular lat/lon grid
            nx = self._geo_keys.get('Ni')
            ny = self._geo_keys.get('Nj')
        elif self._grid_type in ('reduced_gg', 'reduced_ll'):  # reduced global gaussian grid
            ny = self._geo_keys.get('Nj')
            nx = self._geo_keys.get('numberOfValues') / ny

        shape = (nx, ny)
        return shape

    def __init__(self, gid):

        self._lats = self._longs = None
        self._logger = Logger.get_logger()
        self._gid = gid
        self._geo_keys = self._extract_info_keys(gid)
        self._grid_type = self._geo_keys.get('gridType')
        self._points_meridian = self._geo_keys.get('Nj')
        self._missing_value = self._geo_keys.get('missingValue')
        self._shape = self._getShape()
        # lazy computation
        self._lats = None
        self._longs = None

        self._grid_id = self._build_id(gid, self._grid_type)

        self._grid_details_2nd = None
        self._change_resolution_step = None

    def set_2nd_resolution(self, grid2nd, step_range_):
        self._log('Grib resolution changes at key ' + str(step_range_))
        self._grid_details_2nd = grid2nd
        self._change_resolution_step = step_range_
        # change of points along meridian!
        self._points_meridian = grid2nd.getNumberOfPointsAlongMeridian()

    def get_2nd_resolution(self):
        return self._grid_details_2nd

    def get_change_res_step(self):
        return self._change_resolution_step

    def _compute_latlongs(self, gid):

        # method to use with scipy interpolation methods
        # in this case, lats/lons of reduced grids will be expanded

        iterid = gribapi.grib_iterator_new(gid, 0)
        lats = []
        lons = []
        while 1:
            result = gribapi.grib_iterator_next(iterid)
            if not result:
                break
            (lat, lon, value) = result
            lats.append(lat)
            lons.append(lon)
        gribapi.grib_iterator_delete(iterid)
        latsf = np.asarray(lats)
        lonsf = np.asarray(lons)
        lats = lons = None
        return latsf, lonsf

    @property
    def latlons(self):
        # this method is called only when interpolation is a scipy method
        if self._lats is None:
            self._lats, self._longs = self._compute_latlongs(self._gid)
        return self._lats, self._longs

    @staticmethod
    def _extract_info_keys(gid):

        working_keys = {}
        if gribapi.grib_is_defined(gid, 'gridType'):
            working_keys['gridType'] = gribapi.grib_get_string(gid, 'gridType')

        if gribapi.grib_is_defined(gid, 'radius'):
            working_keys['radius'] = gribapi.grib_get_double(gid, 'radius')

        if gribapi.grib_is_defined(gid, 'numberOfValues'):
            working_keys['numberOfValues'] = gribapi.grib_get_long(gid, 'numberOfValues')

        if gribapi.grib_is_defined(gid, 'Ni'):
            working_keys['Ni'] = gribapi.grib_get_long(gid, 'Ni')

        if gribapi.grib_is_defined(gid, 'Nj'):
            working_keys['Nj'] = gribapi.grib_get_long(gid, 'Nj')

        if gribapi.grib_is_defined(gid, 'missingValue'):
            working_keys['missingValue'] = gribapi.grib_get_double(gid, 'missingValue')

        return working_keys

    def getShape(self):
        return self._lats.shape

    def getGridType(self):
        return self._grid_type

    def getGridId(self):
        return self._grid_id

    def getNumberOfPointsAlongMeridian(self):
        return self._points_meridian