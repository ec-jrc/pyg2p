import gribapi as GRIB
import numpy as np
from util.logger.Logger import Logger
import gribpcraster.application.ExecutionContext as ex

#TODO AVOID USAGE OF grib_get. Build id and infos with extractWorkingKeys once!


def _buildId(gid, grid_type):

    if GRIB.grib_is_missing(gid,'Ni'):
        ni='MISSING'
    else :
        ni=GRIB.grib_get(gid, 'Ni')
    if GRIB.grib_is_missing(gid,'Nj'):
        nj='MISSING'
    else:
        nj = GRIB.grib_get(gid, 'Nj')
    num_of_values = GRIB.grib_get(gid, 'numberOfValues')
    long_first = ('%.4f' % (GRIB.grib_get_double(gid, 'longitudeOfFirstGridPointInDegrees'),)).rstrip('0').rstrip('.')
    long_last = ('%.4f' % (GRIB.grib_get_double(gid, 'longitudeOfLastGridPointInDegrees'),)).rstrip('0').rstrip('.')
    return long_first+'$'+long_last+'$'+str(ni)+'$'+str(nj)+'$'+str(num_of_values)+'$'+str(grid_type)

class GribGridDetails(object):

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def _getShape(self):
        nx = ny = 0
        if self._grid_type in ('regular_gg','regular_ll','rotated_ll','rotated_gg'):  # regular lat/lon grid
            nx = self._geo_keys.get('Ni')
            ny = self._geo_keys.get('Nj')
        elif self._grid_type in ('reduced_gg', 'reduced_ll'):  # reduced global gaussian grid
            ny = self._geo_keys.get('Nj')
            nx = self._geo_keys.get('numberOfValues')/ny

        shape = (nx, ny)
        return shape

    def __init__(self, gid):

        #Managed grid types:
        #regular_gg, regular_ll, reduced_ll, reduced_gg, rotated_ll, rotated_gg
        import gribpcraster.application.ExecutionContext as ex
        #ex.global_logger_level
        self._lats = self._longs = None
        self._logger = Logger('Messages', loggingLevel=ex.global_logger_level)
        self._gid = gid
        self._geo_keys = self._extract_info_keys(gid)
        self._grid_type = self._geo_keys.get('gridType')
        self._points_meridian = self._geo_keys.get('Nj')
        self._missing_value = self._geo_keys.get('missingValue')
        self._shape = self._getShape()
        #lazy computation
        self._lats = None
        self._longs = None

        self._grid_id = _buildId(gid,self._grid_type)

        self._grid_details_2nd = None
        self._change_resolution_step = None

    def set_2nd_resolution(self, grid2nd, step_range_):
        self._log('Grib resolution changes at key '+str(step_range_))
        self._grid_details_2nd = grid2nd
        self._change_resolution_step = step_range_
        #change of points along meridian!
        self._points_meridian = grid2nd.getNumberOfPointsAlongMeridian()

    def get_2nd_resolution(self):
        return self._grid_details_2nd

    def get_change_res_step(self):
        return self._change_resolution_step

#method to use with interpolation methods different from grib_nearest and grib_invdist
#in this case, lats/lons of reduced grids will be expanded

    def _computeLatLongs(self, gid):

        iterid = GRIB.grib_iterator_new(gid, 0)
        lats = []
        lons = []
        while 1:
            result = GRIB.grib_iterator_next(iterid)
            if not result:
                break
            (lat, lon, value) = result
            lats.append(lat)
            lons.append(lon)
        GRIB.grib_iterator_delete(iterid)
        latsf = np.asarray(lats)
        lonsf = np.asarray(lons)
        lats = lons = None
        return latsf, lonsf

    #this method is called only when interpolation is a scipy method
    def getLatLons(self):
        if self._lats is None:
            self._lats, self._longs = self._computeLatLongs(self._gid)
        return self._lats, self._longs

    def _extract_info_keys(self, gid):

        working_keys = {}
        if GRIB.grib_is_defined(gid, 'gridType'):
            working_keys['gridType'] = GRIB.grib_get_string(gid, 'gridType')

        if GRIB.grib_is_defined(gid, 'radius'):
            working_keys['radius'] = GRIB.grib_get_double(gid, 'radius')

        if GRIB.grib_is_defined(gid, 'numberOfValues'):
            working_keys['numberOfValues'] = GRIB.grib_get_long(gid, 'numberOfValues')

        if GRIB.grib_is_defined(gid, 'Ni'):
            working_keys['Ni'] = GRIB.grib_get_long(gid, 'Ni')

        if GRIB.grib_is_defined(gid, 'Nj'):
            working_keys['Nj'] = GRIB.grib_get_long(gid, 'Nj')

        if GRIB.grib_is_defined(gid, 'missingValue'):
            working_keys['missingValue'] = GRIB.grib_get_double(gid, 'missingValue')

        return working_keys

    def getShape(self):
        return self._lats.shape

    def getGridType(self):
        return self._grid_type

    def getGridId(self):
        return self._grid_id

    def getNumberOfPointsAlongMeridian(self):
        return self._points_meridian