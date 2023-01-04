from math import radians
from sys import stdout

import eccodes
import numexpr as ne
import numpy as np
import math 
import scipy.optimize as opt  
from scipy.spatial import cKDTree as KDTree

from ...exceptions import ApplicationException, WEIRD_STUFF, INVALID_INTERPOL_METHOD
from pyg2p.util.numeric import mask_it, empty
from pyg2p.util.generics import progress_step_and_backchar
from pyg2p.util.strings import now_string

DEBUG_BILINEAR_INTERPOLATION = False
# DEBUG_MIN_LAT = 88
# DEBUG_MIN_LON = -180
# DEBUG_MAX_LAT = 90
# DEBUG_MAX_LON = 180
# DEBUG_MIN_LAT = 40
# DEBUG_MIN_LON = 5
# DEBUG_MAX_LAT = 50
# DEBUG_MAX_LON = 10
DEBUG_MIN_LAT = 39
DEBUG_MIN_LON = 42
DEBUG_MAX_LAT = 42
DEBUG_MAX_LON = 47
#DEBUG_NN = 15410182


###########################################################################################
###### functions used to get correct quadrilateral points for the bilinear interpolation ####
###########################################################################################

# return lon1, lon2, lon3 and lon4 in classical longitude format range (-180,180)
# furthermore, when differences between lon_in and p points are >90 degree, 
# get the p point on the opposite longitude of the globe
def get_correct_lats_lons(lat_in, lon_in, latgrib, longrib, i1, i2, i3, i4):
    lat = np.zeros((4))
    lon = np.zeros((4))
    for n,i in enumerate([i1,i2,i3,i4]):
        lat[n] = latgrib[i]
        lon[n] = longrib[i]
        # set lon as the same lon_in reference system        
        if lon[n] > 180:
            lon[n] = lon[n]-360
    
    # then change all to -360,0 or 0,360 if needed (otherwise use the current -180,180 reference system)
    if lon_in<-90:
        # use the reference system with lon in range [-360, 0]
        for n in range(4):
            if lon[n] > 0:
                lon[n] -= 360
    elif lon_in>90:
        # use the reference system with lon in range [0, 360]
        for n in range(4):
            if lon[n] < 0:
                lon[n] += 360
    
    for n,i in enumerate([i1,i2,i3,i4]):
        # when differences between lon_in and p points are >90 degree, consider p point on the opposite longitude of the globe
        if abs(lon_in-lon[n])>90:
            lat[n] = 180*np.sign(latgrib[i]) - latgrib[i]
            lon[n] = (lon[n] + 180) % 360
            if lon[n] > 180:
                lon[n] = lon[n]-360

    # then change again to -360 or +360 if needed (otherwise use the current -180,180 reference system)
    if lon_in<-90:
        # use the reference system with lon in range [-360, 0]
        for n in range(4):
            if lon[n] > 0:
                lon[n] -= 360
    elif lon_in>90:
        # use the reference system with lon in range [0, 360]
        for n in range(4):
            if lon[n] < 0:
                lon[n] += 360

    return lat, lon

# given the 4 corner points, store points in p1, p2, p3, p4 vars in clockwise order
def get_clockwise_points(corners_points):        
    # I need to differentiate when 3 points are on the same longitude
    ordered_corners_points = corners_points[0:4, 1]*1000+corners_points[0:4, 0]  
    idx_ordered_points = np.argsort(ordered_corners_points, None)

    left = corners_points[idx_ordered_points[0:2], :]
    right = corners_points[idx_ordered_points[2:4], :]
    if (left[0, 0] <= left[1, 0]):
        bottom_left = left[0, :]
        top_left = left[1, :]
    else:
        bottom_left = left[1, :]
        top_left = left[0, :]

    if right[0, 0] <= right[1, 0]:
        bottom_right = right[0, :]
        top_right = right[1, :]
    else:
        bottom_right = right[1, :]
        top_right = right[0, :]

    return np.array(bottom_left), np.array(bottom_right), np.array(top_right), np.array(top_left)

# check to get exacly only one point for each direction
# returns the wrong point index, if any
# (the wrong point will be the farthest one in latitude only (weighted to longitude value), 
# to favorite grid-like points)
def getWrongPointDirection(lat_in, lon_in, corners_points):
    w=0.01   # weight of longitude component direction compared to latitude one, to favourite grid-like points
    # check to get exacly only two points up and two down
    distances_points_up = corners_points[corners_points[:,0]<=lat_in]-[lat_in,lon_in,0,0]
    points_to_return = []
    while distances_points_up.shape[0]>2:
        point_to_return = distances_points_up[np.argmax(abs(distances_points_up[:,0])+w*abs(distances_points_up[:,1])),3]
        points_to_return.append(point_to_return)
        distances_points_up = np.delete(distances_points_up, np.where(distances_points_up[:,3] == point_to_return), axis=0)
    distances_points_down = corners_points[corners_points[:,0]>lat_in]-[lat_in,lon_in,0,0]
    while distances_points_down.shape[0]>2:
        point_to_return = distances_points_down[np.argmax(abs(distances_points_down[:,0])+w*abs(distances_points_down[:,1])),3]
        points_to_return.append(point_to_return)
        distances_points_down = np.delete(distances_points_down, np.where(distances_points_down[:,3] == point_to_return), axis=0)
    return points_to_return

# check points in grid-like shape
# returns the wrong point index, if any
# (the wrong point will be the farthest one in latitude only, to favorite grid-like points)
def getWrongPointGridLikeShape(lat_in, lon_in, corners_points):
    distances_points_up = corners_points[corners_points[:,0]<=lat_in]-[lat_in,lon_in,0,0]
    distances_points_down = corners_points[corners_points[:,0]>lat_in]-[lat_in,lon_in,0,0]
    eps=0.1*abs(corners_points[:,0]-lat_in).min()
    max_lat_above_point = np.argmax(-distances_points_up[:,0])
    max_lat_below_point = np.argmax(distances_points_down[:,0])
    # check if we have two points on different latitude above the current point
    if abs(distances_points_up[max_lat_above_point,0]-distances_points_up[1-max_lat_above_point,0])>eps:
        return distances_points_up[max_lat_above_point,3]
    # check if we have two points on different latitude below the current point
    if abs(distances_points_down[max_lat_below_point,0]-distances_points_down[1-max_lat_below_point,0])>eps:
        return distances_points_down[max_lat_below_point,3]
    return None


# check points in best grid-like shape
# returns the wrong point index, if any
# starting from the two vertex closer to the current point, check that the other
# two vertex are all above or all below the two closer vertex in longitude
def getWrongPointBestGridLikeShape(lat_in, lon_in, corners_points):        
    # get closest longitude point
    distances_points = abs(corners_points[:,:]-[lat_in,lon_in,0,0])
    closer_lon_point = corners_points[np.argmin(distances_points[:,1])]

    # get the point below, closer to the one above
    distances_points_down = corners_points[corners_points[:,0]>lat_in]-[lat_in,closer_lon_point[1],0,0]
    min_lon_below_point = np.argmin(abs(distances_points_down[:,1]))
    # evaluate the distance
    distance_below = distances_points_down[min_lon_below_point,1] - distances_points_down[1-min_lon_below_point,1]

    # get the point above, closer to the one below
    distances_points_up = corners_points[corners_points[:,0]<=lat_in]-[lat_in,closer_lon_point[1],0,0]
    min_lon_above_point = np.argmin(abs(distances_points_up[:,1]))
    distance_above = distances_points_up[min_lon_above_point,1] - distances_points_up[1-min_lon_above_point,1]

    # check if the two points are on the same side compared to the segment of the closest vertex
    if distance_below*distance_above<0:
        # they fall in opposite directions, thus exclude the fartest one (in longitude)
        if abs(distance_below)>=abs(distance_above):
            preferred_points_to_exclude = distances_points_down[1-min_lon_below_point,3], distances_points_up[1-min_lon_above_point,3] 
            preferred_points_to_include = distances_points_down[min_lon_below_point,3], distances_points_up[min_lon_above_point,3] 
        else:
            preferred_points_to_exclude = distances_points_up[1-min_lon_above_point,3], distances_points_down[1-min_lon_below_point,3] 
            preferred_points_to_include = distances_points_up[min_lon_above_point,3], distances_points_down[min_lon_below_point,3] 
        # check if point to keep is in triangle, otherwise exclude it instead of the preferred one
        if isPointInTriangle([lat_in,lon_in],
                corners_points[abs(corners_points[:,3]-preferred_points_to_exclude[1])<0.5][0,0:2],
                corners_points[abs(corners_points[:,3]-distances_points_up[min_lon_above_point,3])<0.5][0,0:2],
                corners_points[abs(corners_points[:,3]-distances_points_down[min_lon_below_point,3])<0.5][0,0:2]):
            lat_preferred=corners_points[abs(corners_points[:,3]-preferred_points_to_include[0])<0.5][0,0]
            lon_preferred=2*corners_points[abs(corners_points[:,3]-preferred_points_to_include[0])<0.5][0,1] - \
                corners_points[abs(corners_points[:,3]-preferred_points_to_exclude[0])<0.5][0,1]
            return preferred_points_to_exclude[0], lat_preferred, lon_preferred
        else:
            lat_preferred=corners_points[abs(corners_points[:,3]-preferred_points_to_include[1])<0.5][0,0]
            lon_preferred=2*corners_points[abs(corners_points[:,3]-preferred_points_to_include[1])<0.5][0,1] - \
                corners_points[abs(corners_points[:,3]-preferred_points_to_exclude[1])<0.5][0,1]
            return preferred_points_to_exclude[1], lat_preferred, lon_preferred
        

    return None, None, None

# Return the intersection point of line segments `s1` and `s2`, or
# None if they do not intersect.
def intersection(s1, s2):
    p, r = s1[0], s1[1] - s1[0]
    q, s = s2[0], s2[1] - s2[0]
    rxs = float(np.cross(r, s))
    if rxs == 0: return None
    t = np.cross(q - p, s) / rxs
    u = np.cross(q - p, r) / rxs
    if 0 < t < 1 and 0 < u < 1:
        return p + t * r
    return None

# check if vertex make a convex quadrilateral
def isConvexQuadrilateral(p1, p2, p3, p4):
    diagonal_intersectin = intersection([p1, p3],[p2, p4])
    return diagonal_intersectin is not None

# get angle between segments ab and bc (used to get the non convex vertex)
def get_angle(a, b, c):
    angle = math.degrees(math.atan2(c[1]-b[1], c[0]-b[0]) - math.atan2(a[1]-b[1], a[0]-b[0]))
    return angle + 360 if angle < 0 else angle

# get index of the non convex vertex
def getNonConvexVertex(p1, p2, p3, p4):
    if get_angle(p1[0:2],p2[0:2],p3[0:2]) >= 179.9:
        return p2[3]
    if get_angle(p2[0:2],p3[0:2],p4[0:2]) >= 179.9:
        return p3[3]
    if get_angle(p3[0:2],p4[0:2],p1[0:2]) >= 179.9:
        return p4[3]
    if get_angle(p4[0:2],p1[0:2],p2[0:2]) >= 179.9:
        return p1[3]
    return None #we should never get here

# used in the point in triangle check
def sign(p1, p2, p3):
    return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])

# check if point pt is in triangle with vertex v1,v2,v3
def isPointInTriangle(pt, v1, v2, v3):
    d1 = sign(pt, v1, v2)
    d2 = sign(pt, v2, v3)
    d3 = sign(pt, v3, v1)

    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)

    return not(has_neg and has_pos)

# if a quadrilateral is convex, check if point pt is inside the quatrilater
# n.b: is the quadrilateral is not convex, just switch the vertex in this way:
# if (is_convex) or (index_nonconvex!=self.p2[3] and index_nonconvex!=self.p4[3]):
#       is_in_quadrilateral = isPointInQuadrilateral([self.lat_in,self.lon_in], self.p1[0:2], self.p2[0:2], self.p3[0:2], self.p4[0:2])
#   else:
#       is_in_quadrilateral = self.isPointInQuadrilateral([self.lat_in,self.lon_in], self.p2[0:2], self.p3[0:2], self.p4[0:2], self.p1[0:2])   
def isPointInQuadrilateral(pt, v1, v2, v3, v4, is_convex):
    assert(is_convex) # I should never call this on non convex quatrilaters
    is_in_t1 = isPointInTriangle(pt, v1,v2,v3)
    is_in_t2 = isPointInTriangle(pt, v1,v4,v3)
    return is_in_t1 or is_in_t2


class ScipyInterpolation(object):
    """
    http://docs.scipy.org/doc/scipy/reference/spatial.html
    """
    gribapi_version = list(map(int, eccodes.codes_get_api_version().split('.')))
    rotated_bugfix_gribapi = gribapi_version[0] > 1 or (gribapi_version[0] == 1 and gribapi_version[1] > 14) or (gribapi_version[0] == 1 and gribapi_version[1] == 14 and gribapi_version[2] >= 3)

    def __init__(self, longrib, latgrib, grid_details, source_values, nnear, 
                    mv_target, mv_source, target_is_rotated=False, parallel=False,
                    bilinear=False):
        stdout.write('Start scipy interpolation: {}\n'.format(now_string()))
        self.geodetic_info = grid_details
        self.source_grid_is_rotated = 'rotated' in grid_details.get('gridType')
        self.target_grid_is_rotated = target_is_rotated
        self.njobs = 1 if not parallel else -1
        
        self.longrib = longrib
        self.latgrib = latgrib
        self.nnear = nnear
        self.bilinear = bilinear
        
        # we receive rotated coords from GRIB_API iterator before 1.14.3
        x, y, zz = self.to_3d(longrib, latgrib, to_regular=not self.rotated_bugfix_gribapi)
        source_locations = np.vstack((x.ravel(), y.ravel(), zz.ravel())).T
        try:
            assert len(source_locations) == len(source_values), "len(coordinates) {} != len(values) {}".format(len(source_locations), len(source_values))
        except AssertionError as e:
            ApplicationException.get_exc(WEIRD_STUFF, details=str(e))

        stdout.write('Building KDTree...\n')
        self.tree = KDTree(source_locations, leafsize=30)  # build the tree
        self.z = source_values

        self._mv_target = mv_target
        self._mv_source = mv_source
        # we can calculate resolution in KM as described here:
        # http://math.boisestate.edu/~wright/montestigliano/NearestNeighborSearches.pdf
        # sphdist = R*acos(1-maxdist^2/2);
        # Finding actual resolution of source GRID
        distances, indexes = self.tree.query(source_locations, k=2, n_jobs=self.njobs)
        # set max of distances as min upper bound and add an empirical correction value
        self.min_upper_bound = np.max(distances) + np.max(distances) * 4 / self.geodetic_info.get('Nj')

    def interpolate(self, target_lons, target_lats):
        # Target coordinates  HAVE to be rotated coords in case GRIB grid is rotated
        # Example of target rotated coords are COSMO lat/lon/dem PCRASTER maps
        self.target_latsOR=target_lats
        self.target_lonsOR=target_lons
        x, y, z = self.to_3d(target_lons, target_lats, to_regular=self.target_grid_is_rotated)
        efas_locations = np.vstack((x.ravel(), y.ravel(), z.ravel())).T
        stdout.write('Finding indexes for ' + ('nearest neighbour' if self.bilinear == False else 'bilinear interpolation') + ' k={}\n'.format(self.nnear))

        distances, indexes = self.tree.query(efas_locations, k=self.nnear, n_jobs=self.njobs) 
        
        if self.nnear == 1:
            # return distances, distances, indexes
            result, indexes = self._build_nn(distances, indexes)
            weights = distances
        else:
            if self.bilinear == False: 
                # return distances, distances, indexes
                result, weights, indexes = self._build_weights_invdist(distances, indexes, self.nnear) 
            else:  
                if self.nnear == 4: # bilinear interpolation only supported with nnear = 4
                    # BILINEAR INTERPOLATION
                    result, weights, indexes = self._build_weights_bilinear(distances, indexes, efas_locations, self.nnear) 
                    ##print (result,weights)         
                else:
                    raise ApplicationException.get_exc(INVALID_INTERPOL_METHOD, 
                                f"bilinear interpolation only supported with nnear = 4, used {self.nnear}")
                    
               
        stdout.write('End scipy interpolation: {}\n'.format(now_string()))
        return result, weights, indexes

    def to_3d(self, lons, lats, rotate=False, to_regular=False):
        # these variables are used. Do NOT remove as they are used by numexpr
        lons = np.radians(lons)
        lats = np.radians(lats)
        x_formula = 'cos(lons) * cos(lats)'
        y_formula = 'sin(lons) * cos(lats)'
        z_formula = 'sin(lats)'

        if to_regular:
            teta = - radians((90 + self.geodetic_info.get('latitudeOfSouthernPoleInDegrees')))
            fi = - radians(self.geodetic_info.get('longitudeOfSouthernPoleInDegrees'))
            x = ne.evaluate('(cos(teta) * cos(fi) * ({x})) + (sin(fi)  * ({y})) + (sin(teta) * cos(fi) * ({z}))'.format(x=x_formula, y=y_formula, z=z_formula))
            y = ne.evaluate('(cos(teta) * sin(fi) * ({x})) + (cos(fi)  * ({y})) - (sin(teta) * sin(fi) * ({z}))'.format(x=x_formula, y=y_formula, z=z_formula))
            z = ne.evaluate('(-sin(teta) * ({x})) + (cos(teta) * ({z}))'.format(x=x_formula, z=z_formula))
        elif rotate:
            teta = radians((90 + self.geodetic_info.get('latitudeOfSouthernPoleInDegrees')))
            fi = radians(self.geodetic_info.get('longitudeOfSouthernPoleInDegrees'))
            x = ne.evaluate('(cos(teta) * cos(fi) * ({x})) + (cos(teta) * sin(fi) * ({y})) + (sin(teta) * ({z}))'.format(x=x_formula, y=y_formula, z=z_formula))
            y = ne.evaluate('(-sin(fi) * ({x})) + (cos(fi) * ({y}))'.format(x=x_formula, y=y_formula))
            z = ne.evaluate('(-sin(teta) * cos(fi) * ({x})) - (sin(teta) * sin(fi) * ({y})) + (cos(teta) * ({z}))'.format(x=x_formula, y=y_formula, z=z_formula))
        else:
            r = self.geodetic_info.get('radius')
            x = ne.evaluate('r * {x}'.format(x=x_formula))
            y = ne.evaluate('r * {y}'.format(y=y_formula))
            z = ne.evaluate('r * {z}'.format(z=z_formula))
        return x, y, z

    def _build_nn(self, distances, indexes):
        z = self.z
        result = mask_it(np.empty((len(distances),) + np.shape(z[0])), self._mv_target, 1)
        jinterpol = 0
        num_cells = result.size
        back_char, progress_step = progress_step_and_backchar(num_cells)
        stdout.write('Skipping neighbors at distance > {}\n'.format(self.min_upper_bound))
        stdout.write('{}Building coeffs: 0/{} [outs: 0] (0%)'.format(back_char, num_cells))
        stdout.flush()

        idxs = empty((len(indexes),), fill_value=z.size, dtype=int)
        # wsum will be saved in intertable
        outs = 0
        for dist, ix in zip(distances, indexes):
            if jinterpol % progress_step == 0:
                stdout.write('{}Building coeffs: {}/{} [outs: {}] ({:.2f}%)'.format(back_char, jinterpol, num_cells, outs, jinterpol * 100. / num_cells))
                stdout.flush()
            if dist <= self.min_upper_bound:
                wz = z[ix]
                idxs[jinterpol] = ix
            else:
                # stdout.write('\nneighbour discarded. distance: {}\n'.format(dist))
                outs += 1
                wz = self._mv_target
            result[jinterpol] = wz
            jinterpol += 1
        stdout.write('{}{:>100}'.format(back_char, ' '))
        stdout.write('{}Building coeffs: {}/{} [outs: {}] (100%)\n'.format(back_char, jinterpol, num_cells, outs))
        stdout.flush()
        return result, idxs

    def _build_weights_invdist(self, distances, indexes, nnear):
        z = self.z
        result = mask_it(np.empty((len(distances),) + np.shape(z[0])), self._mv_target, 1)
        jinterpol = 0
        num_cells = result.size
        back_char, progress_step = progress_step_and_backchar(num_cells)

        stdout.write('Skipping neighbors at distance > {}\n'.format(self.min_upper_bound))
        stdout.write('{}Building coeffs: 0/{} [outs: 0] (0%)'.format(back_char, num_cells))
        stdout.flush()

        # weights will be saved in intertable along with indexes
        weights = empty((len(distances),) + (nnear,))
        idxs = empty((len(indexes),) + (nnear,), fill_value=z.size, dtype=int)
        empty_array = empty(z[0].shape, self._mv_target)
        outs = 0
        for dist, ix in zip(distances, indexes):
            if jinterpol % progress_step == 0:
                stdout.write('{}Building coeffs: {}/{} [outs: {}] ({:.2f}%)'.format(back_char, jinterpol, num_cells, outs, jinterpol * 100. / num_cells))
                stdout.flush()
            if dist[0] <= 1e-10:
                wz = z[ix[0]]  # take exactly the point, weight = 1
                idxs[jinterpol] = ix
                weights[jinterpol] = np.array([1., 0., 0., 0.])
            elif dist[0] <= self.min_upper_bound:
                w = ne.evaluate('1 / dist ** 2')
                sums = ne.evaluate('sum(w)')
                ne.evaluate('w/sums', out=w)
                wz = np.dot(w, z[ix])  # weighted values (result)
                weights[jinterpol] = w
                idxs[jinterpol] = ix
            else:
                outs += 1
                weights[jinterpol] = np.array([1., 0., 0., 0.])
                wz = empty_array
            result[jinterpol] = wz
            jinterpol += 1
        stdout.write('{}{:>100}'.format(back_char, ' '))
        stdout.write('{}Building coeffs: {}/{} [outs: {}] (100%)\n'.format(back_char, jinterpol, num_cells, outs))
        stdout.flush()
        return result, weights, idxs

    # take additional points from the KDTree close to the current point and replace the wrong ones with a new ones
    def replaceIndex(self, indexes_to_replace, indexes, nn, additional_points):
        additional_points += len(indexes_to_replace)
        # replace the unwanted index with next one:
        _, replacement_indexes = self.tree.query(self.target_location, k=self.nnear+additional_points, n_jobs=self.njobs) 
        # print("replacement_indexes: {}".format(replacement_indexes))

        # delete all the current indexes from the replaceent_indexes 
        # this is to fix an issue with the query, that do not give always the same
        # order when the distance is the same for some of the points
        for i in indexes[nn, 0:4]:
            replacement_indexes = np.delete(replacement_indexes, np.where(replacement_indexes == i))
        
        # get rid of the wrong point and add the farthest among the new selected points
        for n,i in enumerate(indexes_to_replace):
            indexes[nn, indexes[nn, 0:4] == i] = replacement_indexes[-(n+1)]
        if len(np.unique(indexes[nn, 0:4]))!=4:
            print("Less then 4 distinct point!")
        return additional_points
    
    # take up to 2 additional points from the KDTree close to the another point on the opposite side 
    # and replace the wrong ones with new ones
    def replaceIndexOppositeSide(self, indexes_to_replace, indexes, nn):
        self.replaceIndexCloseToPoint(indexes_to_replace, 180-self.lat_in, self.lon_in, indexes, nn)

    # take additional points from the KDTree close to the another specific point
    # and replace the wrong ones with new ones
    def replaceIndexCloseToPoint(self, indexes_to_replace, new_lat, new_lon, indexes, nn):
        # replace up to 2 unwanted indexes with next ones:
        x, y, z = self.to_3d(new_lon, new_lat, to_regular=self.target_grid_is_rotated)
        new_target_location = [x,y,z]
        _, replacement_indexes = self.tree.query(new_target_location, k=len(indexes_to_replace), n_jobs=self.njobs) 
        # print("replacement_indexes: {}".format(replacement_indexes))
        
        # get rid of the wrong points and add the farthest among the new selected points
        if len(indexes_to_replace)>1:
            for n,i in enumerate(indexes_to_replace):
                indexes[nn, indexes[nn, 0:4] == i] = replacement_indexes[-(n+1)]
        else:
            indexes[nn, indexes[nn, 0:4] == indexes_to_replace[0]] = replacement_indexes

        if len(np.unique(indexes[nn, 0:4]))!=4:
            print("Less then 4 distinct point!")

    def _build_weights_bilinear(self, distances, indexes, efas_locations, nnear):
        z = self.z
        result = mask_it(np.empty((len(distances),) +
                         np.shape(z[0])), self._mv_target, 1)
        weights = np.empty((len(distances),) + (nnear,))
        idxs = empty((len(indexes),) + (nnear,), fill_value=z.size, dtype=int)
        weight1 = empty((len(distances),))
        weight2 = empty((len(distances),))
        weight3 = empty((len(distances),))
        weight4 = empty((len(distances),))
        empty_array = empty(z[0].shape, self._mv_target)

        self.lat_inALL = self.target_latsOR.ravel()
        self.lon_inALL = self.target_lonsOR.ravel()

        num_cells = result.size
        back_char, progress_step = progress_step_and_backchar(num_cells)

        stdout.write('Skipping bilinear interpolation at distance > {}\n'.format(self.min_upper_bound))
        stdout.write('{}Building coeffs: 0/{} [outs: 0] (0%)'.format(back_char, num_cells))
        stdout.flush()

        outs = 0    #number of points falling outside the min_upper_bound distance

        # max number of retry equals to a full lenght of lon coordinates
        max_retries = self.target_lonsOR.shape[0]        
        max_used_additional_points = 0
        nn_max_used_additional_points = -1

        latgrib_max = self.latgrib.max()
        latgrib_min = self.latgrib.min()
        #for nn in range(1810762,len(indexes)):
        for nn in range(len(indexes)):
            if nn % progress_step == 0:
                stdout.write('{}Building coeffs: {}/{} [outs: {}] ({:.2f}%)'.format(back_char, nn, num_cells, outs, nn * 100. / num_cells))
                stdout.flush()

            dist = distances[nn]
            ix = indexes[nn]
            self.lat_in = self.lat_inALL[nn]
            self.lon_in = self.lon_inALL[nn]

            # if DEBUG_BILINEAR_INTERPOLATION:
            #     # # if nn==14753:
            #     # if nn==72759:
            # if nn==185623:
            #     print('self.lat_in = {}, self.lon_in = {}, nn = {}'.format(self.lat_in,self.lon_in,nn))
            #     if abs(self.lat_in-40.775)<0.02 and abs(self.lon_in-44.825)<0.02:
            #         print('self.lat_in = {}, self.lon_in = {}, nn = {}'.format(self.lat_in,self.lon_in,nn))

            # check distances 
            if dist[0] <= 1e-10:  
                result[nn] = z[ix[0]]  # take exactly the point, weight = 1
                idxs[nn] = ix
                weights[nn] = np.array([1., 0., 0., 0.])
            elif dist[0] > self.min_upper_bound:
                outs += 1
                weights[nn] = np.array([1., 0., 0., 0.])
                result[nn] = empty_array
            else:
                self.target_location = efas_locations[nn]
                additional_points = 0
                quadrilateral_is_ok = False
                # additional checks only if source_grid_is_rotated is False
                if self.source_grid_is_rotated == False:
                    additional_checks_completed = False
                else:
                    additional_checks_completed = True
                    max_retries = 20
                while quadrilateral_is_ok == False and additional_points<max_retries:  
                    # find the 4 corners
                    i1, i2, i3, i4 = indexes[nn, 0:4]
                    idxs[nn, :] = indexes[nn, 0:4]

                    # check the point on lat lon coords system:
                    # I need that my location falls in the quadrilateral
                    # (actually the quadrilateral should be convex as per bilinear interpolation (bilinear warp) definition,
                    # but the interpolation works also on non-convex poligon
                    # N.B: when the quadrilateral is not a rectangle, we have a so called "bilinear transformation, 
                    # bilinear warp or bilinear distortion", instead of a bilinear interpolation. 
                    # See : https://en.wikipedia.org/wiki/Bilinear_interpolation

                    lats, lons = get_correct_lats_lons(self.lat_in, self.lon_in, self.latgrib, self.longrib, i1, i2, i3, i4)

                    corners_points = np.array([[lats[0], lons[0], self.z[i1], i1],
                        [lats[1], lons[1], self.z[i2], i2],
                        [lats[2], lons[2], self.z[i3], i3],
                        [lats[3], lons[3], self.z[i4], i4]])

                    # check grib type (if grig is on parallels or projected (self.source_grid_is_rotated=True))
                    # in case we are not in parallel-like grib files, let's use the old bilinear method 
                    # that works with every grid but is less precise
                    # see here for possible grib files https://apps.ecmwf.int/codes/grib/format/grib1/grids/10/
                    if additional_checks_completed == False:
                        # the grib file has different number of longitude points for each latitude,
                        # thus I will make sure to use only 2 above and two below of the current point
                        # the function will return the wrong point, if any
                        index_wrong_points = getWrongPointDirection(self.lat_in, self.lon_in, corners_points)
                        if len(index_wrong_points):
                            # check if the latitude point is above the maximum or below the minimun latitude, 
                            # to speed up the process and retrieve better "close points" from the KDTree 
                            # I will look for nearest points of the opposite side of the globe
                            if self.lat_in>latgrib_max or self.lat_in<latgrib_min:
                                self.replaceIndexOppositeSide(index_wrong_points, indexes, nn)
                            else:
                                additional_points = self.replaceIndex(index_wrong_points, indexes, nn, additional_points)
                        else:
                            # check for points in grid-like shape
                            index_wrong_point = getWrongPointGridLikeShape(self.lat_in, self.lon_in, corners_points)
                            if index_wrong_point is not None:
                                additional_points = self.replaceIndex([index_wrong_point], indexes, nn, additional_points)
                            else:
                                # check for best grid-like shape:
                                index_wrong_point, new_lat, new_lon = getWrongPointBestGridLikeShape(self.lat_in, self.lon_in, corners_points)
                                if index_wrong_point is not None:
                                    self.replaceIndexCloseToPoint([index_wrong_point], new_lat, new_lon, indexes, nn)
                                else:
                                    additional_checks_completed = True
                    if additional_checks_completed == True:
                        #get p1,p2,p3,p4 in clockwise order
                        self.p1, self.p2, self.p3, self.p4 = get_clockwise_points(corners_points)
                        # check for convexity
                        is_convex = isConvexQuadrilateral(self.p1[0:2], self.p2[0:2], self.p3[0:2], self.p4[0:2])
                        index_nonconvex = -1
                        if is_convex == False:                            
                            index_nonconvex = getNonConvexVertex(self.p1, 
                                                    self.p2, 
                                                    self.p3, 
                                                    self.p4,)
                            if (index_nonconvex is None):
                                print("Error, index_nonconvex is None for nn={}".format(nn))
                            
                            assert(index_nonconvex is not None)    
                            additional_points = self.replaceIndex([index_nonconvex], indexes, nn, additional_points)
                        else:
                            # check for point in quadrilateral
                            is_in_quadrilateral = isPointInQuadrilateral([self.lat_in,self.lon_in], 
                                                                            self.p1[0:2], 
                                                                            self.p2[0:2], 
                                                                            self.p3[0:2], 
                                                                            self.p4[0:2], 
                                                                            is_convex)
                            if is_in_quadrilateral == False:
                                # get rid of the wrong point (the actual farthest one) and add the new one 
                                # (that is the farthest in the new list of replacement_indexes)
                                additional_points = self.replaceIndex([indexes[nn, 3]], indexes, nn, additional_points)                                
                            else:
                                quadrilateral_is_ok = True

                if max_used_additional_points<additional_points:
                    max_used_additional_points = additional_points
                    nn_max_used_additional_points = nn
                    print("\nmax_used_additional_points: {}, nn_max_used_additional_points: {}".format(max_used_additional_points, nn_max_used_additional_points))

                try:
                    assert(quadrilateral_is_ok == True)                    
                except AssertionError as e:
                    ApplicationException.get_exc(WEIRD_STUFF, details=str(e) + "\nError: quadrilateral_is_ok is False, failed to find a correct quadrilateral: nn is {}, lat={} lon={}".format(nn, self.lat_in, self.lon_in))

                try:
                    assert(len(np.unique(indexes[nn, 0:4]))==4) 
                except AssertionError as e:
                    ApplicationException.get_exc(WEIRD_STUFF, details=str(e) + "\nLess then 4 distinct point! nn={} lat={} lon={}".format(nn, self.lat_in, self.lon_in))
                
                if quadrilateral_is_ok==False:
                    print("\nError: quadrilateral_is_ok is False, failed to find a correct quadrilateral: nn is {}, lat={} lon={}".format(nn, self.lat_in, self.lon_in))

                [alpha, beta] = np.clip(opt.fsolve(self._functionAlphaBeta, (0.5, 0.5)), 0, 1)
                weight1[nn] = (1-alpha)*(1-beta)
                weight2[nn] = alpha*(1-beta)
                weight3[nn] = alpha*beta
                weight4[nn] = (1-alpha)*beta

                weights[nn, 0:4] = np.array([weight1[nn], weight2[nn], weight3[nn], weight4[nn]])
                idxs[nn, 0:4] = np.array([self.p1[3], self.p2[3], self.p3[3], self.p4[3]])
                result[nn] = weight1[nn]*self.p1[2] + weight2[nn]*self.p2[2] + weight3[nn] * self.p3[2] + weight4[nn] * self.p4[2]  

        stdout.write('{}{:>100}'.format(back_char, ' '))
        stdout.write('{}Building coeffs: {}/{} [outs: {}] (100%)\n'.format(back_char, num_cells, num_cells, outs))
        stdout.write('debug info: max_used_additional_points is {}, nn is {}\n'.format(max_used_additional_points, nn_max_used_additional_points))
        stdout.flush()

        return result, weights, idxs

    def _functionAlphaBeta(self, variables):
        (alpha, beta) = variables
        # This is the function that we want to make 0
        first_eq = (1-alpha)*(1-beta)*self.p1[0]+alpha*(
            1-beta)*self.p2[0]+alpha*beta*self.p3[0]+(1-alpha)*beta*self.p4[0]-self.lat_in
        second_eq = (1-alpha)*(1-beta)*self.p1[1]+alpha*(
            1-beta)*self.p2[1]+alpha*beta*self.p3[1]+(1-alpha)*beta*self.p4[1]-self.lon_in
        return [first_eq, second_eq]
