import gribapi as GRIB
import numpy as np
from util.logger.Logger import Logger
import gribpcraster.application.ExecutionContext as ex

def _getShape(gid, grid_type_, numValues):
    nx = ny = 0
    if grid_type_ in ('regular_gg','regular_ll','rotated_ll','rotated_gg'):  # regular lat/lon grid
        nx = GRIB.grib_get(gid, 'Ni')
        ny = GRIB.grib_get(gid, 'Nj')
    elif grid_type_ in ('reduced_gg', 'reduced_ll'):  # reduced global gaussian grid
        ny = GRIB.grib_get(gid, 'Nj')
        nx = numValues/ny

    shape = (nx, ny)
    return shape

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

    def __init__(self, gid):

        #Managed grid types:
        #regular_gg, regular_ll, reduced_ll, reduced_gg, rotated_ll, rotated_gg
        import gribpcraster.application.ExecutionContext as ex
        #ex.global_logger_level
        self._lats = self._longs = None
        self._logger = Logger('Messages', loggingLevel=ex.global_logger_level)
        self._gid = gid
        self._grid_type = GRIB.grib_get(gid, 'gridType')
        self._geo_keys = self._extractWorkingKeys(gid)
        self._missing_value = GRIB.grib_get(gid, 'missingValue')
        self._shape = _getShape(gid, self._grid_type, GRIB.grib_get(gid, 'numberOfValues'))
        #lazy computation
        self._lats = None
        self._longs = None

        self._grid_id = _buildId(gid,self._grid_type)
        self._points_meridian = GRIB.grib_get(gid,'Nj')

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

    def get_geo_keys(self):
        return self._geo_keys

#method to use with interpolation methods different from grib_nearest and grib_invdist
#in this case, lats/lons of reduced grids will be expanded to regular ones.
#  Values will be expanded to regular grids as well (not implemented yet)

    # def _latlons(self, gid):
    #     if self._grid_type in ('regular_gg','regular_ll'): # regular lat/lon grid
    #         nx = GRIB.grib_get(gid,'Ni')
    #         ny = GRIB.grib_get(gid,'Nj')
    #         lon1 = GRIB.grib_get(gid,'longitudeOfFirstGridPointInDegrees')
    #         lon2 = GRIB.grib_get(gid,'longitudeOfLastGridPointInDegrees')
    #
    #         if lon1 >= 0 and lon2 < 0 and self.iDirectionIncrement > 0:
    #             lon2 = 360+lon2
    #         if lon1 >= 0 and lon2 < lon1 and self.iDirectionIncrement > 0:
    #             lon1 = lon1-360
    #         lat1 = self['latitudeOfFirstGridPointInDegrees']
    #         lat2 = self['latitudeOfLastGridPointInDegrees']
    #     # workaround for grib_api bug with complex packing.
    #     # (distinctLongitudes, distinctLatitudes throws error,
    #     #  so use np.linspace to define values)
        #     if self.packingType.startswith('grid_complex'):
        #         # this is not strictly correct for gaussian grids,
        #         # but the error is very small.
        #         lats = np.linspace(lat1,lat2,ny)
        #         lons = np.linspace(lon1,lon2,nx)
        #     else:
        #         lats = self['distinctLatitudes']
        #         if lat2 < lat1 and lats[-1] > lats[0]: lats = lats[::-1]
        #         lons = self['distinctLongitudes']
        #         # don't trust distinctLongitudes
        #         # when longitudeOfLastGridPointInDegrees < 0
        #         # (bug in grib_api 1.9.16)
        #         if lon2 < 0:
        #             lons = np.linspace(lon1,lon2,nx)
        #             lons,lats = np.meshgrid(lons,lats)
    #
    #     elif self._grid_type == 'reduced_gg': # reduced global gaussian grid
    #
    #         lat1 = self['latitudeOfFirstGridPointInDegrees']
    #         lat2 = self['latitudeOfLastGridPointInDegrees']
    #         lats = self['distinctLatitudes']
    #         if lat2 < lat1 and lats[-1] > lats[0]: lats = lats[::-1]
    #         ny = self['Nj']
    #         nx = 2*ny
    #         lon1 = self['longitudeOfFirstGridPointInDegrees']
    #         lon2 = self['longitudeOfLastGridPointInDegrees']
    #         lons = np.linspace(lon1,lon2,nx)
    #         lons,lats = np.meshgrid(lons,lats)
    #
    #     elif self._grid_type == 'reduced_ll': # reduced lat/lon grid
    #
    #         ny = self['Nj']
    #         nx = 2*ny
    #         lat1 = self['latitudeOfFirstGridPointInDegrees']
    #         lat2 = self['latitudeOfLastGridPointInDegrees']
    #         lon1 = self['longitudeOfFirstGridPointInDegrees']
    #         lon2 = self['longitudeOfLastGridPointInDegrees']
    #         lons = np.linspace(lon1,lon2,nx)
    #         lats = np.linspace(lat1,lat2,ny)
    #         lons,lats = np.meshgrid(lons,lats)



    def _computeLatLongs(self, gid):

        # if self._grid_type == 'reduced_gg': # reduced global gaussian grid
        #
        #     lat1 = GRIB.grib_get(gid, 'latitudeOfFirstGridPointInDegrees')
        #     lat2 = GRIB.grib_get(gid, 'latitudeOfLastGridPointInDegrees')
        #     lon1 = GRIB.grib_get(gid, 'longitudeOfFirstGridPointInDegrees')
        #     lon2 = GRIB.grib_get(gid,'longitudeOfLastGridPointInDegrees')
        #     ny = GRIB.grib_get(gid, 'Nj')
        #     nx = 2*ny
        #     lats = GRIB.grib_get_double_array(gid,'latitudes')
        #     lons = GRIB.grib_get_double_array(gid,'longitudes')
        #     if lat2 < 0:
        #         # raw_input('l1 '+str(lat1))
        #         # raw_input('l2 '+str(lat2))
        #         # raw_input('l1 '+str(lats[0]))
        #         # raw_input('l2 '+str(lats[-1]))
        #         # lats = lats[::-1]
        #         # raw_input('l1 '+str(lats[0]))
        #         # raw_input('l2 '+str(lats[-1]))
        #         lats = lats + lats[-1]
        #         # raw_input('l1 '+str(lats[0]))
        #         # raw_input('l2 '+str(lats[-1]))
        #     # lonsf = np.linspace(lon1, lon2, nx)
        #     latsf = lats
        #     lonsf = lons
        #     # lonsf,latsf = np.meshgrid(lonsf,latsf)
        #
        # else:
        iterid = GRIB.grib_iterator_new(gid, 0)
        lats = []
        lons = []
        i = 0
        while 1:
            result = GRIB.grib_iterator_next(iterid)
            if not result:
                break
            (lat, lon, value) = result
            lats.append(lat)
            lons.append(lon)
        GRIB.grib_iterator_delete(iterid)

        # latsd = GRIB.grib_get_double_array(gid, 'distinctLatitudes')
        # if l2 < l1:
        #     raw_input(str(latsd[-1])+ ' - ' +str(latsd[0])+ '-'+str(latsd[-1] > latsd[0]))
        #     lats = lats[::-1]

        latsf = np.asarray(lats)
        lonsf = np.asarray(lons)
        lats = lons = None
        return latsf, lonsf

    #this method is called only when interpolation is a scipy method
    def getLatLons(self):
        if self._lats is None:
            self._lats, self._longs = self._computeLatLongs(self._gid)
        return self._lats, self._longs

    def _extractWorkingKeys(self, gid):

        working_keys = {}

        if GRIB.grib_is_defined(gid, 'radius'):
            working_keys['radius'] = GRIB.grib_get(gid, 'radius')
        working_keys['shapeOfTheEarth'] = GRIB.grib_get(gid, 'shapeOfTheEarth')
        if GRIB.grib_is_defined(gid, 'scaleFactorOfMajorAxisOfOblateSpheroidEarth'):
            working_keys['scaleFactorOfMajorAxisOfOblateSpheroidEarth'] = GRIB.grib_get(gid,
                                                                                        'scaleFactorOfMajorAxisOfOblateSpheroidEarth')
        if GRIB.grib_is_defined(gid, 'missingValue'):
            working_keys['missingValue'] = GRIB.grib_get_double(gid, 'missingValue')

        # scaleFactorOfRadiusOfSphericalEarth
        if GRIB.grib_is_defined(gid, 'scaleFactorOfRadiusOfSphericalEarth'):
            working_keys['scaleFactorOfRadiusOfSphericalEarth'] = GRIB.grib_get_double(gid,
                                                                                       'scaleFactorOfRadiusOfSphericalEarth')

        # scaledValueOfMajorAxisOfOblateSpheroidEarth
        if GRIB.grib_is_defined(gid, 'scaledValueOfMajorAxisOfOblateSpheroidEarth'):
            working_keys['scaledValueOfMajorAxisOfOblateSpheroidEarth'] = GRIB.grib_get_double(gid,
                                                                                               'scaledValueOfMajorAxisOfOblateSpheroidEarth')
            # scaleFactorOfMinorAxisOfOblateSpheroidEarth
        if GRIB.grib_is_defined(gid, 'scaleFactorOfMinorAxisOfOblateSpheroidEarth'):
            working_keys['scaleFactorOfMinorAxisOfOblateSpheroidEarth'] = GRIB.grib_get_double(gid,
                                                                                               'scaleFactorOfMinorAxisOfOblateSpheroidEarth')
            # scaledValueOfEarthMajorAxis
        if GRIB.grib_is_defined(gid, 'scaledValueOfEarthMajorAxis'):
            working_keys['scaledValueOfEarthMajorAxis'] = GRIB.grib_get_double(gid, 'scaledValueOfEarthMajorAxis')
            # scaledValueOfEarthMinorAxis
        if GRIB.grib_is_defined(gid, 'scaledValueOfEarthMinorAxis'):
            working_keys['scaledValueOfEarthMinorAxis'] = GRIB.grib_get_double(gid, 'scaledValueOfEarthMinorAxis')

        # scaledValueOfRadiusOfSphericalEarth
        if GRIB.grib_is_defined(gid, 'scaledValueOfRadiusOfSphericalEarth'):
            working_keys['scaledValueOfRadiusOfSphericalEarth'] = GRIB.grib_get_double(gid,
                                                                                       'scaledValueOfRadiusOfSphericalEarth')
            # standardParallel
        if GRIB.grib_is_defined(gid, 'standardParallel'):
            working_keys['standardParallel'] = GRIB.grib_get_double(gid, 'standardParallel')
            # centralLongitude
        if GRIB.grib_is_defined(gid, 'centralLongitude'):
            working_keys['centralLongitude'] = GRIB.grib_get_double(gid, 'centralLongitude')
            # angleOfRotationInDegrees
        if GRIB.grib_is_defined(gid, 'angleOfRotationInDegrees'):
            working_keys['angleOfRotationInDegrees'] = GRIB.grib_get_double(gid, 'angleOfRotationInDegrees')
            # latitudeOfSouthernPoleInDegrees
        if GRIB.grib_is_defined(gid, 'latitudeOfSouthernPoleInDegrees'):
            working_keys['latitudeOfSouthernPoleInDegrees'] = GRIB.grib_get_double(gid,
                                                                                   'latitudeOfSouthernPoleInDegrees')
            # longitudeOfSouthernPoleInDegrees
        if GRIB.grib_is_defined(gid, 'longitudeOfSouthernPoleInDegrees'):
            working_keys['longitudeOfSouthernPoleInDegrees'] = GRIB.grib_get_double(gid, 'longitudeOfSouthernPoleInDegrees')

        return working_keys

    def getShape(self):
        return self._lats.shape

    def getGridType(self):
        return self._grid_type

    def getGridId(self):
        return self._grid_id

    def getNumberOfPointsAlongMeridian(self):
        return self._points_meridian