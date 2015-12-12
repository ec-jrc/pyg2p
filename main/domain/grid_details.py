import gribapi
import numpy as np

from util.logger import Logger


class GribGridDetails(object):
    """
    # Managed grid types:
        * regular_gg, regular_ll
        * reduced_ll, reduced_gg (include octahedral grid)
        * rotated_ll, rotated_gg

    """

    keys = (('gridType', 'string'), ('radius', 'double'), ('numberOfValues', 'long'),
            ('Ni', 'long'), ('Nj', 'long'), ('missingValue', 'double'),
            ('longitudeOfFirstGridPointInDegrees', 'double'), ('longitudeOfLastGridPointInDegrees', 'double'),)
    check_for_missing_keys = ('Ni', 'Nj',)

    def __init__(self, gid):

        self._logger = Logger.get_logger()
        self._gid = gid
        self._geo_keys = {
            key_: getattr(gribapi, 'grib_get_{}'.format(type_))(gid, key_)
            for key_, type_ in self.keys
            if gribapi.grib_is_defined(gid, key_)
        }
        self._missing_keys = {
            key_: 'MISSING'
            for key_ in self.check_for_missing_keys
            if gribapi.grib_is_missing(gid, key_)
        }
        self._grid_type = self._geo_keys.get('gridType')
        self._points_meridian = self._geo_keys.get('Nj')
        self._missing_value = self._geo_keys.get('missingValue')
        self._grid_id = self._build_id()
        # lazy computation
        self._lats = None
        self._longs = None

        self._grid_details_2nd = None
        self._change_resolution_step = None

    def _build_id(self):
        ni = 'MISSING' if 'Ni' in self._missing_keys else self._geo_keys.get('Ni')  # if gribapi.grib_is_missing(gid, 'Ni') else self._geo_keys.get('Ni')
        nj = 'MISSING' if 'Nj' in self._missing_keys else self._geo_keys.get('Nj')  # if gribapi.grib_is_missing(gid, 'Nj') else self._geo_keys.get('Nj')
        num_of_values = self._geo_keys.get('numberOfValues')
        long_first = ('%.4f' % (self._geo_keys.get('longitudeOfFirstGridPointInDegrees'),)).rstrip('0').rstrip('.')
        long_last = ('%.4f' % (self._geo_keys.get('longitudeOfLastGridPointInDegrees'),)).rstrip('0').rstrip('.')
        grid_id = '{}${}${}${}${}${}'.format(long_first, long_last, ni, nj, num_of_values, self._grid_type)
        return grid_id

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def set_2nd_resolution(self, grid2nd, step_range_):
        self._log('Grib resolution changes at key {}'.format(step_range_))
        self._grid_details_2nd = grid2nd
        self._change_resolution_step = step_range_
        # change of points along meridian!
        self._points_meridian = grid2nd.num_points_along_meridian

    def get_2nd_resolution(self):
        return self._grid_details_2nd

    def get_change_res_step(self):
        return self._change_resolution_step

    @staticmethod
    def _compute_latlongs(gid):

        # method to use with scipy interpolation methods
        # in this case, lats/lons of reduced grids will be expanded
        lats = gribapi.grib_get_double_array(gid, 'latitudes')
        lons = gribapi.grib_get_double_array(gid, 'longitudes')
        return lats, lons

    @property
    def latlons(self):
        # this method is called only when interpolation is a scipy method
        if self._lats is None:
            self._log('Fetching coordinates from grib file')
            self._lats, self._longs = self._compute_latlongs(self._gid)
        return self._lats, self._longs

    @property
    def grid_id(self):
        return self._grid_id

    @property
    def num_points_along_meridian(self):
        return self._points_meridian
