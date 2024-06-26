from math import radians
from sys import stdout
import time

import eccodes
import numexpr as ne
import numpy as np
import math 
import scipy.optimize as opt  
from scipy.spatial import cKDTree as KDTree, Delaunay

from pyg2p.main.readers.netcdf import NetCDFReader
from pyg2p.main.readers.pcr import PCRasterReader

from ...exceptions import ApplicationException, WEIRD_STUFF, INVALID_INTERPOL_METHOD
from pyg2p.util.numeric import mask_it, empty
from pyg2p.util.generics import progress_step_and_backchar
from pyg2p.util.strings import now_string

#from matplotlib import pyplot as plt
from scipy.integrate import quad

from numba import njit


DEBUG_BILINEAR_INTERPOLATION = False
DEBUG_ADW_INTERPOLATION = False
# DEBUG_MIN_LAT = 88
# DEBUG_MIN_LON = -180
# DEBUG_MAX_LAT = 90
# DEBUG_MAX_LON = 180
# DEBUG_MIN_LAT = 40
# DEBUG_MIN_LON = 5
# DEBUG_MAX_LAT = 50
# DEBUG_MAX_LON = 10
# DEBUG_MIN_LAT = 68
# DEBUG_MIN_LON = -24
# DEBUG_MAX_LAT = 70
# DEBUG_MAX_LON = -22
# DEBUG_MIN_LAT = -10
# DEBUG_MIN_LON = -100
# DEBUG_MAX_LAT = 25
# DEBUG_MAX_LON = -50
# DEBUG_MIN_LAT = 7
# DEBUG_MIN_LON = 45
# DEBUG_MAX_LAT = 9
# DEBUG_MAX_LON = 50
# DEBUG_MIN_LAT = (45.31663-2)
# DEBUG_MIN_LON = (0.46648-2) #0.50048
# DEBUG_MAX_LAT = (45.31663+2)
# DEBUG_MAX_LON = (0.46648+2) #0.50048
# DEBUG_MIN_LAT = (45.31663-2)
# DEBUG_MIN_LON = (0.50048-2) 
# DEBUG_MAX_LAT = (45.31663+2)
# DEBUG_MAX_LON = (0.50048+2) 
# lat 45.28263, lon 0.45948
# DEBUG_MIN_LAT = (45.28263-2)
# DEBUG_MIN_LON = (0.45948-2) 
# DEBUG_MAX_LAT = (45.28263+2)
# DEBUG_MAX_LON = (0.45948+2) 
# lat 45.28263 lon 0.5517

# DEBUG_MIN_LAT = (45.28263-40)
# DEBUG_MIN_LON = (0.5517-60) 
# DEBUG_MAX_LAT = (45.28263+40)
# DEBUG_MAX_LON = (0.5517+60) 

# Full European 1arcmin, step 0.01666666666667993:
# DEBUG_MIN_LAT = 22.758333333333333
# DEBUG_MIN_LON = -25.241666666666667
# DEBUG_MAX_LAT = 72.24166666666667
# DEBUG_MAX_LON = 50.24166666666666
DEBUG_MIN_LAT = 45-10
DEBUG_MIN_LON = 8-10
DEBUG_MAX_LAT = 45+10
DEBUG_MAX_LON = 8+10
# DEBUG_MIN_LAT = 57.95-0
# DEBUG_MIN_LON = 16.80-0
# DEBUG_MAX_LAT = 57.95+5
# DEBUG_MAX_LON = 16.80+5

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
    # check special case of two point that have exacly the same lat and lon
    pointslist=corners_points[:,0:2]
    if len(np.unique(pointslist, axis=0, return_index=True)[1])!=4:
        points_to_return = []
        for i in range(4):
            if i not in np.unique(pointslist, axis=0, return_index=True)[1]:
                points_to_return.append(corners_points[i,3])
        return points_to_return
        
    
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

# used in triangulation for the evaluation of space between vertical grid in grib non regular grid files
def integrand(x):
    return 1/np.cos(x)


@njit(parallel=True, fastmath=False, cache=True)
def adw_compute_weights_from_cutoff_distances(distances, s, ref_radius):
    # get "s" vector as the inverse distance with power = 1 (in "w" we have the invdist power 2)
    # actually s(d) should be 
    #   1/d                     when 0 < d <= r'/3
    #   (27/4r')*[(d/r'-1)^2]   when r'/3 < d <= r'
    #   0                       when r' < d
    # The orginal method consider a range of 4 to 10 data points e removes distant point using the rule:
    # pi*r= 7(N/A)  where N id the number of points and A is the area of the largest poligon enclosed by data points
    # r'(C^n) = di(n+1) where di is the Point having the minimum distance major than the first n Points
    # so that
    #   r' = r' C^4 = di(5)     when n(C) <= 4
    #   r' = r                  when 4 < n(C) <= 10
    #   r' = r' C^10 = di(11)   when 10 < n(C)
    #
    # evaluate r from pi*r= 7(N/A):
    # A = area of the polygon containing all points
    # N = number of points
    # trick: I can evaluate r from the KD Tree of distances: r should be the radius that contains 7 points as an average
    # so I can set it as the value that contains 70% of the whole distance dataset.
    # Given the ordered distances struct, the quickest way to do it is to evaluate the average of all distances of the 7th 
    # element of the distance arrays
    
    if ref_radius==None:
        r_ref = np.mean(distances[:, 6])
    else:
        r_ref = ref_radius 
    
    # prepare r, initialize with di(11):                 
    r = distances[:, 10].copy()
    # evaluate r' for each point. to do that, 
    # 1) chech if the distance in the fourth position is higher that r_ref, if so, we are in case r' C^4 (that is = di(5))
    
    r_1_flag = distances[:, 3] > r_ref
    # copy the corresponding fifth distance di(5) as the radius
    r[r_1_flag] = distances[r_1_flag, 4]
    # 2) check if n(C)>4 and n(C)<=10
    r_2_flag = np.logical_and(~r_1_flag, distances[:, 9] > r_ref)
    # copy r as the radius
    r[r_2_flag] = r_ref
    # 3) all the other case, n(C)>10, will be equal to di(11) (already set at the initialization, so do nothing here)
    
    # apply the distance rule based on the radiuses
    r_broadcasted = r.reshape(-1,1)
    
    #   1/d                     when 0 < d <= r'/3
    dist_leq_r3 = distances <= r_broadcasted / 3
    s.ravel()[dist_leq_r3.ravel()] = 1. / distances.ravel()[dist_leq_r3.ravel()]
    
    #   (27/4r')*(d/r'-1)       when r'/3 < d <= r'
    dist_g_r3_leq_r = np.logical_and(~dist_leq_r3, distances <= r_broadcasted)
    s.ravel()[dist_g_r3_leq_r.ravel()] = ((27 / (4 * r_broadcasted)) * ((distances / r_broadcasted - 1) ** 2)).ravel()[dist_g_r3_leq_r.ravel()]
    
    #   0                       when r' < d  (keep the default zero value)

    # in case of Shepard we use the square of the coeafficient stored later in variable "s"
    w = s ** 2
    return w, s

@njit(parallel=True, fastmath=False, cache=True)
def cdd_hofstra_compute_weights_from_cutoff_distances(distances, CDD_map, s):
    # Hofstra et al. 2008 
    # CDD is the correlation distance decay to get the serach radius

    # formula for weights:
    # where m is fixed to 4 and x is the distance between the station i and the point 
    m_const = 4.0 # constant
    # wi = [e^(−x/CDD)]^m       when 0  < d <= CDD
    #   0                       when CDD < d
    # The orginal method consider a range of 3 to 10 data points e removes distant points
    #

    # 1) chech if the distance in the third position is higher that CDD, if so, we should store a missing value
    # because it means we don't have a minimum of 3 points within the CDD radius
    missingval_flag = distances[:, 2] > CDD_map
    
    # apply the distance rule based on the radiuses
    CDD_broadcasted = CDD_map.reshape(-1,1)
    
    #   [e^(−x/CDD)]^m       when 0  < d <= CDD
    dist_leq_CDD = distances <= CDD_broadcasted
    s.ravel()[dist_leq_CDD.ravel()] = np.exp(-distances*m_const/CDD_broadcasted).ravel()[dist_leq_CDD.ravel()]
        
    #   0                       when CDD < d  (keep the default zero value)

    s[missingval_flag] = 0
    return s

@njit(parallel=True, fastmath=False, cache=True)
def cdd_hofstra_shepard_compute_weights_from_cutoff_distances(distances, CDD_map, nnear, s, m_const = 4, min_num_of_station = 4, radius_ratio=1/3):
    # mix Hofstra and Shepard methods 
    # uses Shepard approach to smooth borders:
    #   wi = [e^(−x/CDD)]^m                                             when 0  < d <= CDD*radius_ratio  e^(-radius_ratio)^m
    #   [1/(radius_ratio-1)^2]*{[e^(-radius_ratio)]^m}*[(d/CDD-1)^2]    when CDD*radius_ratio < d <= CDD  
    #   0                                                               when CDD < d
    # furthermore, as in Shepard, increases adjust radius value in these cases:
    #   having n(C) number of points having distance < CDD
    #   r' = r' C^min_num_of_station = di(min_num_of_station+1)     when n(C) <= min_num_of_station
    #   r' = CDD                when min_num_of_station < n(C) <= 10    n.b: 10 = [nnear-1]
    #   r' = r' C^10 = di(11)   when 10 < n(C)                          n.b: 10 = [nnear-1]

    r_ref = CDD_map
    # prepare r, initialize with di(11) [nnear]:
    #r = distances[:, 10].copy()
    r = distances[:, nnear-1].copy()
    # evaluate r' for each point. to do that, 
    # 1) chech if the distance in the fourth position is higher that r_ref, if so, we are in case r' C^min_num_of_station (that is = di(min_num_of_station+1))
    r_1_flag = distances[:, min_num_of_station-1] > r_ref
    # copy the corresponding fifth distance di(min_num_of_station+1) as the radius
    r[r_1_flag] = distances[r_1_flag, min_num_of_station]
    # 2) check if n(C)>min_num_of_station and n(C)<=10 [nnear-1]
    #r_2_flag = np.logical_and(~r_1_flag, distances[:, 9] > r_ref)
    r_2_flag = np.logical_and(~r_1_flag, distances[:, nnear-2] > r_ref)
    # copy CDD as the radius
    r[r_2_flag] = r_ref[r_2_flag]
    # 3) all the other case, n(C)>10 [nnear-1], will be equal to di(11) (already set at the initialization, so do nothing here)
    
    # apply the distance rule based on the radiuses
    r_broadcasted = r.reshape(-1,1)
    
    #   wi = [e^(−x/CDD)]^m     when 0 < d <= CDD*radius_ratio  e^(-radius_ratio)^m
    dist_leq_r3 = distances <= r_broadcasted * radius_ratio
    s.ravel()[dist_leq_r3.ravel()] = np.exp(-distances*m_const/r_broadcasted).ravel()[dist_leq_r3.ravel()]
    
    #   [1/(radius_ratio-1)^2]*{[e^(-radius_ratio)]^m}*[(d/CDD-1)^2]   when CDD*radius_ratio < d <= CDD
    dist_g_r3_leq_r = np.logical_and(~dist_leq_r3, distances <= r_broadcasted)
    s.ravel()[dist_g_r3_leq_r.ravel()] = (( (1/(radius_ratio-1)**2) * np.exp(-m_const*radius_ratio)) * ((distances / r_broadcasted - 1) ** 2)).ravel()[dist_g_r3_leq_r.ravel()]
    
    #   0                       when r' < d  (keep the default zero value)
    return s


@njit(parallel=True, fastmath=False, cache=True)
def cdd_newetal_compute_weights_from_cutoff_distances(distances, CDD_map, indexes, longrib, latgrib, TargetLonRes, TargetLatRes, LonOrigin, LatOrigin, s):
    # New et al. 2000 
    # no search radius applied
    # consider all the available nearest station, and use their respective CDD to compute the weights

    # formula for weights:
    # where m is fixed to 4 and x is the distance between the station i and the point 
    m_const = 4.0 # constant
    # wi = [e^(−x/CDD)]^m       
        
    #   [e^(−x/CDD)]^m       when 0  < d <= CDD

    CDD_values = CDD_map[np.clip(((LatOrigin-latgrib[indexes])/TargetLatRes).astype(int),0,CDD_map.shape[0]-1), \
                                        np.clip(((LonOrigin-longrib[indexes])/TargetLonRes).astype(int),0,CDD_map.shape[1]-1)]
    dist_leq_CDD = distances <= CDD_values
    s.ravel()[dist_leq_CDD.ravel()] = np.exp(-distances*m_const/CDD_values).ravel()[dist_leq_CDD.ravel()]
        
    return s

@njit(parallel=True, fastmath=False, cache=True)
def adw_and_cdd_compute_weights_directional_in_broadcasting(
    s,latgrib,longrib,indexes,lat_inALL,lon_inALL):
    # All in broadcasting: 
    # this algorithm uses huge amount of memory and deas not speed up much on standard Virtual Machine
    if DEBUG_ADW_INTERPOLATION:
        print("\nUsing full broadcasting")
    # Compute xi and yi for all elements
    k=indexes.shape[1]
    xi = latgrib.ravel()[indexes.ravel()]
    yi = longrib.ravel()[indexes.ravel()]
    # Compute xi_diff and yi_diff for all elements
    xi_diff = lat_inALL.reshape(-1,1) - xi.reshape(-1,k)
    yi_diff = lon_inALL.reshape(-1,1) - yi.reshape(-1,k)
    # Compute Di for all elements
    Di = np.sqrt(xi_diff**2 + yi_diff**2)
    # Compute cos_theta for all elements
    cos_theta = (xi_diff.reshape(-1,k,1)* xi_diff.reshape(-1,1,k) + yi_diff.reshape(-1,k,1) * yi_diff.reshape(-1,1,k)) / (Di.reshape(-1,k,1) * Di.reshape(-1,1,k))
    # skip when i==j, so that directional weight of i is evaluated on all points j where j!=i 
    # TODO: tip: since cos_theta = 1 for i==j, to speed up we can skip this passage and apply i!=j only on denominator
    # Delete the diagonal elements from cos_theta
    # Reshape cos_theta to (n, nnear, nnear-1)
    n = cos_theta.shape[0]
    m = cos_theta.shape[1]
    strided = np.lib.stride_tricks.as_strided
    s0,s1,s2 = cos_theta[:].strides
    cos_theta = strided(cos_theta.ravel()[1:], shape=(n,m-1,m), strides=(s0,s1+s2,s2)).copy().reshape(n,m,-1)
    sj = s.T.repeat(k).reshape(k,-1,k).transpose(1,2,0).copy()
    s0,s1,s2 = sj[:].strides
    sj = strided(sj.ravel()[1:], shape=(n,m-1,m), strides=(s0,s1+s2,s2)).copy().reshape(n,m,-1)
    # sj = np.tile(s[:, np.newaxis, :], (1, m, 1))
    # s0,s1,s2 = sj[:].strides
    # sj = strided(sj.ravel()[1:], shape=(n,m-1,m), strides=(s0,s1+s2,s2)).reshape(n,m,-1)

    numerator = np.sum((1 - cos_theta) * sj, axis=2)
    denominator = np.sum(sj, axis=2)
    # Compute weight_directional for all elements
    weight_directional = numerator / denominator
    
    return weight_directional


class ScipyInterpolation(object):
    """
    http://docs.scipy.org/doc/scipy/reference/spatial.html
    """
    gribapi_version = list(map(int, eccodes.codes_get_api_version().split('.')))
    rotated_bugfix_gribapi = gribapi_version[0] > 1 or (gribapi_version[0] == 1 and gribapi_version[1] > 14) or (gribapi_version[0] == 1 and gribapi_version[1] == 14 and gribapi_version[2] >= 3)

    def __init__(self, longrib, latgrib, grid_details, source_values, nnear, 
                    mv_target, mv_source, target_is_rotated=False, parallel=False,
                    mode='nearest', cdd_map='', cdd_mode='', cdd_options = None, use_broadcasting = False,
                    num_of_splits = None):
        stdout.write('Start scipy interpolation: {}\n'.format(now_string()))
        self.geodetic_info = grid_details
        self.source_grid_is_rotated = 'rotated' in grid_details.get('gridType')
        self.target_grid_is_rotated = target_is_rotated
        self.njobs = 1 if not parallel else -1
        
        self.longrib = longrib
        self.latgrib = latgrib
        self.nnear = nnear
        self.mode = mode
        self.cdd_map = cdd_map
        self.cdd_mode = cdd_mode
        self.cdd_options = cdd_options
        self.use_broadcasting = use_broadcasting
        self.num_of_splits = num_of_splits
        
        if DEBUG_ADW_INTERPOLATION:
            self.use_broadcasting = True

        self._mv_target = mv_target
        self._mv_source = mv_source
        self.z = source_values
        
        # we receive rotated coords from GRIB_API iterator before 1.14.3
        x, y, zz = self.to_3d(longrib, latgrib, to_regular=not self.rotated_bugfix_gribapi)
        source_locations = np.vstack((x.ravel(), y.ravel(), zz.ravel())).T
        try:
            assert len(source_locations) == len(source_values), "len(coordinates) {} != len(values) {}".format(len(source_locations), len(source_values))
        except AssertionError as e:
            ApplicationException.get_exc(WEIRD_STUFF, details=str(e))

        stdout.write('Building KDTree...\n')
        self.tree = KDTree(source_locations, leafsize=30)  # build the tree

        if self.mode == "adw":
            self.min_upper_bound = None # not used in adw (Shepard) algorithm
        else:
            # we can calculate resolution in KM as described here:
            # http://math.boisestate.edu/~wright/montestigliano/NearestNeighborSearches.pdf
            # sphdist = R*acos(1-maxdist^2/2);
            # Finding actual resolution of source GRID
            distances, indexes = self.tree.query(source_locations, k=2, workers=self.njobs)
            # set max of distances as min upper bound and add an empirical correction value
            self.min_upper_bound = np.max(distances) + np.max(distances) * 4 / self.geodetic_info.get('Nj')

    def interpolate(self, lonefas, latefas):        
        if (self.num_of_splits is not None):
            ref_radius = None
            if self.mode == 'adw' and self.nnear == 11:
                start = time.time()
                stdout.write('Finding global reference radius {} interpolation k=7\n'.format(self.mode))
                x, y, z = self.to_3d(lonefas, latefas, to_regular=self.target_grid_is_rotated)
                efas_locations = np.vstack((x.ravel(), y.ravel(), z.ravel())).T
                distances, indexes = self.tree.query(efas_locations, k=7, workers=self.njobs) 
                if efas_locations.dtype==np.dtype('float32'):
                    distances=np.float32(distances)

                ref_radius=np.mean(distances[:, 6])
                checktime = time.time()
                stdout.write('KDtree find radius time (sec): {}\n'.format(checktime - start))

            # Define the size of the subsets, only in lonm
            subset_size = lonefas.shape[0]//self.num_of_splits

            # Initialize empty arrays to store the results
            weights = np.empty((lonefas.shape[0]*lonefas.shape[1],self.nnear),dtype=lonefas.dtype)
            indexes = np.empty((lonefas.shape[0]*lonefas.shape[1],self.nnear),dtype=int)
            result = np.empty((lonefas.shape[0]*lonefas.shape[1]),dtype=lonefas.dtype)

            # Iterate over the subsets of the arrays
            for i in range(0, lonefas.shape[0], subset_size):
                subset_lonefas = lonefas[i:i+subset_size, :]
                subset_latefas = latefas[i:i+subset_size, :]

                # Call the interpolate function for the subset
                subset_result, subset_weights, subset_indexes = self.interpolate_split(subset_lonefas, subset_latefas, ref_radius)

                # Collect the results back into the weights and indexes arrays
                weights[i*lonefas.shape[1]:(i+subset_size)*lonefas.shape[1],:] = subset_weights
                indexes[i*lonefas.shape[1]:(i+subset_size)*lonefas.shape[1],:] = subset_indexes
                result[i*lonefas.shape[1]:(i+subset_size)*lonefas.shape[1]] = subset_result
        
        else:
            result, weights, indexes = self.interpolate_split(lonefas, latefas)

        return result, weights, indexes


    def interpolate_split(self, target_lons, target_lats, ref_radius=None):        
        # Target coordinates  HAVE to be rotated coords in case GRIB grid is rotated
        # Example of target rotated coords are COSMO lat/lon/dem PCRASTER maps
        self.target_latsOR=target_lats
        self.target_lonsOR=target_lons

        start = time.time()
        if self.mode != 'triangulation' and self.mode != 'bilinear_delaunay':
            stdout.write('Finding indexes for {} interpolation k={}\n'.format(self.mode, self.nnear))
            x, y, z = self.to_3d(target_lons, target_lats, to_regular=self.target_grid_is_rotated)
            efas_locations = np.vstack((x.ravel(), y.ravel(), z.ravel())).T
            distances, indexes = self.tree.query(efas_locations, k=self.nnear, workers=self.njobs) 
            if efas_locations.dtype==np.dtype('float32'):
                distances=np.float32(distances)
            checktime = time.time()
            stdout.write('KDtree time (sec): {}\n'.format(checktime - start))
        
        if self.mode == 'nearest' and self.nnear == 1:
            # return results, indexes
            result, indexes = self._build_nn(distances, indexes)
            weights = distances
        else:
            if self.mode == 'invdist': 
                # return results, distances, indexes
                result, weights, indexes = self._build_weights_invdist(distances, indexes, self.nnear)
            elif self.mode == 'adw' and self.nnear == 11:
                result, weights, indexes = self._build_weights_invdist(distances, indexes, self.nnear, adw_type='Shepard', use_broadcasting=self.use_broadcasting, ref_radius=ref_radius)             
            elif self.mode == 'cdd':
                result, weights, indexes = self._build_weights_invdist(distances, indexes, self.nnear, adw_type='CDD', use_broadcasting=self.use_broadcasting, ref_radius=None,
                                                                       cdd_map=self.cdd_map, cdd_mode=self.cdd_mode, cdd_options=self.cdd_options)
            elif self.mode == 'bilinear' and self.nnear == 4: # bilinear interpolation only supported with nnear = 4
                # BILINEAR INTERPOLATION
                result, weights, indexes = self._build_weights_bilinear(distances, indexes, efas_locations, self.nnear) 
            elif self.mode == 'triangulation':
                # linear barycentric interpolation on Delaunay triangulation
                result, weights, indexes = self._build_weights_triangulation(use_bilinear=False) 
            elif self.mode == 'bilinear_delaunay':
                    # bilinear interpolation on Delaunay triangulation
                    result, weights, indexes = self._build_weights_triangulation(use_bilinear=True) 
            else:
                raise ApplicationException.get_exc(INVALID_INTERPOL_METHOD, 
                            f"interpolation method not supported (mode = {self.mode}, nnear = {self.nnear})")
                    
               
        stdout.write('End scipy interpolation: {}\n'.format(now_string()))
        end = time.time()
        stdout.write('Interpolation time (sec): {}\n'.format(end - start))

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

        if lons.dtype==np.dtype('float32'):
            x=np.float32(x)
            y=np.float32(y)
            z=np.float32(z)

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

    # # Invdist Optimized version (using broadcast)
    # def _build_weights_invdist(self, distances, indexes, nnear):
    #     z = self.z
    #     result = mask_it(np.empty((len(distances),) + np.shape(z[0])), self._mv_target, 1)
    #     weights = empty((len(distances),) + (nnear,))
    #     idxs = empty((len(indexes),) + (nnear,), fill_value=z.size, dtype=int)
    #     num_cells = result.size
    #     back_char, _ = progress_step_and_backchar(num_cells)

    #     stdout.write('Skipping neighbors at distance > {}\n'.format(self.min_upper_bound))
    #     stdout.write('{}Building coeffs: {}/{} ({:.2f}%)\n'.format(back_char, 0, 5, 0, 0))
    #     stdout.flush()

    #     dist_leq_1e_10 = distances[:, 0] <= 1e-10
    #     dist_leq_min_upper_bound = np.logical_and(~dist_leq_1e_10, distances[:, 0] <= self.min_upper_bound)
        
    #     # distances <= 1e-10 : take exactly the point, weight = 1
    #     onlyfirst_array = np.zeros(nnear)
    #     onlyfirst_array[0] = 1
    #     weights[dist_leq_1e_10] = onlyfirst_array
    #     idxs[dist_leq_1e_10] = indexes[dist_leq_1e_10]
    #     result[dist_leq_1e_10] = z[indexes[dist_leq_1e_10][:, 0]]

    #     w = np.zeros_like(distances)
    #     w[dist_leq_min_upper_bound] = 1. / distances[dist_leq_min_upper_bound] ** 2
    #     stdout.write('{}Building coeffs: {}/{} ({:.2f}%)\n'.format(back_char, 1, 5, 100/5))
    #     stdout.flush()
    #     sums = np.sum(w[dist_leq_min_upper_bound], axis=1, keepdims=True)
    #     stdout.write('{}Building coeffs: {}/{} ({:.2f}%)\n'.format(back_char, 2, 5, 2*100/5))
    #     stdout.flush()
    #     weights[dist_leq_min_upper_bound] = w[dist_leq_min_upper_bound] / sums
    #     stdout.write('{}Building coeffs: {}/{} ({:.2f}%)\n'.format(back_char, 3, 5, 3*100/5))
    #     stdout.flush()
    #     wz = np.einsum('ij,ij->i', weights, z[indexes])
    #     stdout.write('{}Building coeffs: {}/{} ({:.2f}%)\n'.format(back_char, 4, 5, 4*100/5))
    #     stdout.flush()
    #     idxs[dist_leq_min_upper_bound] = indexes[dist_leq_min_upper_bound]
    #     result[dist_leq_min_upper_bound] = wz[dist_leq_min_upper_bound]
    #     stdout.write('{}Building coeffs: {}/{} (100%)\n'.format(back_char, 5, 5))
    #     stdout.flush()
    #     return result, weights, idxs

    # Inverse distance weights (IDW) interpolation, with optional Angular distance weighting (ADW) factor
    # if adw_type == None -> simple IDW 
    # if adw_type == Shepard -> Shepard 1968 original formulation
    def _build_weights_invdist(self, distances, indexes, nnear, adw_type = None, use_broadcasting = False, ref_radius = None, 
                               cdd_map='', cdd_mode='', cdd_options=None):
        if DEBUG_ADW_INTERPOLATION:
            if adw_type != "Shepard":
                self.min_upper_bound = 1000000000
            if DEBUG_BILINEAR_INTERPOLATION:
                #n_debug=1940
                #n_debug=3120
                n_debug=1120
            else:
                n_debug=11805340
        z = self.z
        result = mask_it(np.empty((len(distances),) + np.shape(z[0]),dtype=z.dtype), self._mv_target, 1)
        weights = empty((len(distances),) + (nnear,),dtype=z.dtype)
        idxs = empty((len(indexes),) + (nnear,), fill_value=z.size, dtype=int)
        num_cells = result.size
        back_char, _ = progress_step_and_backchar(num_cells)

        stdout.write('Skipping neighbors at distance > {}\n'.format(self.min_upper_bound))
        stdout.write('{}Building coeffs: {}/{} ({:.2f}%)\n'.format(back_char, 0, 5, 0, 0))
        stdout.flush()

        if (adw_type is None):
            dist_leq_1e_10 = distances[:, 0] <= 1e-10
            dist_leq_min_upper_bound = np.logical_and(~dist_leq_1e_10, distances[:, 0] <= self.min_upper_bound)
        
            # distances <= 1e-10 : take exactly the point, weight = 1
            onlyfirst_array = np.zeros(nnear)
            onlyfirst_array[0] = 1
            weights[dist_leq_1e_10] = onlyfirst_array
            idxs[dist_leq_1e_10] = indexes[dist_leq_1e_10]
            result[dist_leq_1e_10] = z[indexes[dist_leq_1e_10][:, 0]]

            w = np.zeros_like(distances)

            # in case of normal IDW we use inverse squared distances
            # while in case of Shepard we use the square of the coeafficient stored later in variable "s"
            # while in case of CDD we use the same Wi coeafficient stored later in variable "s"
            w[dist_leq_min_upper_bound] = 1. / distances[dist_leq_min_upper_bound] ** 2

        stdout.write('{}Building coeffs: {}/{} ({:.2f}%)\n'.format(back_char, 1, 5, 100/5))
        stdout.flush()

        if (adw_type=='Shepard') or (adw_type=='CDD'):
            self.lat_inALL = self.target_latsOR.ravel()
            self.lon_inALL = self.target_lonsOR.ravel()

            if (adw_type=='Shepard'): 
                # this implementation is based on the manuscript by Shepard et al. 1968 
                # now it applies the selection of station, too. k=11 stations are need to perform the full elavaluation

                # initialize weights
                if (use_broadcasting == False):
                    weight_directional = np.zeros_like(distances)
                start = time.time()
                s = np.zeros_like(distances)
                w, s = adw_compute_weights_from_cutoff_distances(distances, s, ref_radius)
                checktime = time.time()
                stdout.write('adw_compute_weights_from_cutoff_distances time (sec): {}\n'.format(checktime - start))

            elif (adw_type=='CDD'):
                # this implementation is based on the manuscript by Hofstra et al. 2008 and New et al. 2000 

                #read CDD map or txt file
                CDD_map = None
                stdout.write(f'Reading CDD values from: {cdd_map}')
                if cdd_map.endswith('.nc'):
                    reader = NetCDFReader(cdd_map)
                else:
                    reader = PCRasterReader(cdd_map)
                # CDD map values are in km, so convert to meters to compare with distances
                CDD_map = reader.values * 1000

                if DEBUG_BILINEAR_INTERPOLATION:
                    # target_lats=target_lats[1800-(9*20):1800-(-16*20), 3600+(-15*20):3600+(16*20)]
                    # target_lons=target_lons[1800-(9*20):1800-(-16*20), 3600+(-15*20):3600+(16*20)]
                    if CDD_map.shape==(3600,7200):
                        # Global_3arcmin DEBUG
                        CDD_map=CDD_map[1800-int(DEBUG_MAX_LAT*20):1800-int(DEBUG_MIN_LAT*20), 3600+int(DEBUG_MIN_LON*20):3600+int(DEBUG_MAX_LON*20)]
                        #latefas-=0.008369999999992217
                        # lonefas-=0.00851999999999431
                        #lonefas-=0.024519999999977227   

                    else:
                        # European_1arcmin DEBUG
                        CDD_map=CDD_map[round((72.24166666666667-DEBUG_MAX_LAT)/0.01666666666667993):round((72.24166666666667-DEBUG_MIN_LAT)/0.01666666666667993), \
                            round((-25.241666666666667-DEBUG_MIN_LON)/-0.01666666666667993):round((-25.241666666666667-DEBUG_MAX_LON)/-0.01666666666667993)]

                #CDDmode = 'NewEtAl'
                #CDDmode = 'Hofstra'
                #CDDmode = 'MixHofstraShepard'       #uses Shepard approach to smooth borders
                CDDmode = cdd_mode
                
                weights_mode = 'All'
                #weights_mode = 'OnlyTOP10'
                if (CDDmode == 'Hofstra'):
                    CDD_map = CDD_map.ravel()
                    try:
                        assert(len(CDD_map)==len(self.lat_inALL)) 
                    except AssertionError as e:
                        ApplicationException.get_exc(WEIRD_STUFF, details=str(e) + "\nCDD map should have the same resolution of target map. CDD map len={}, target map len={}".format(len(CDD_map), len(self.lat_inALL)))

                    stdout.write('\nEvaluating cutoffs...')
                    
                    s = np.zeros_like(distances)       
                    s = cdd_hofstra_compute_weights_from_cutoff_distances(distances, CDD_map, s)
                elif CDDmode == 'MixHofstraShepard':
                    CDD_map = CDD_map.ravel()
                    try:
                        assert(len(CDD_map)==len(self.lat_inALL)) 
                    except AssertionError as e:
                        ApplicationException.get_exc(WEIRD_STUFF, details=str(e) + "\nCDD map should have the same resolution of target map. CDD map len={}, target map len={}".format(len(CDD_map), len(self.lat_inALL)))

                    if DEBUG_ADW_INTERPOLATION:
                        stdout.write('\nEvaluating cutoffs...')
                    
                    s = np.zeros_like(distances)      
                    if cdd_options is None:
                        # Hofstra standard values
                        m_const = 4
                        min_num_of_station = 4
                        radius_ratio = 1/3
                        weights_mode = "All"
                    else:
                        # Custom values
                        m_const, min_num_of_station, radius_ratio, weights_mode = cdd_options.values()
                    cdd_hofstra_shepard_compute_weights_from_cutoff_distances(distances, CDD_map, nnear, s, m_const, min_num_of_station, radius_ratio)
                elif CDDmode == 'NewEtAl':
                    s = np.zeros_like(distances)  
                    TargetLonRes=self.target_lonsOR[0,0]-self.target_lonsOR[0,1]
                    TargetLatRes=self.target_latsOR[0,0]-self.target_latsOR[1,0]
                    LonOrigin=self.target_lonsOR[0,0]
                    LatOrigin=self.target_latsOR[0,0]
                    s = cdd_newetal_compute_weights_from_cutoff_distances(distances, CDD_map, indexes, self.longrib, self.latgrib, 
                                                                        TargetLonRes, TargetLatRes, LonOrigin, LatOrigin, s)
                else:
                    ApplicationException.get_exc(WEIRD_STUFF, "\nCDD mode unknown={}".format(CDDmode))

                # consider only TOP 10 weights instead of all:
                if weights_mode == "OnlyTOP10":
                    # indices of top 10 values in each row
                    #   idx = np.argpartition(s, 10, axis=1)  # get indices of top 10 values
                    #   rows = np.arange(s.shape[0])[:, None]
                    #   s[rows, idx[:, :-10]] = 0
                    # all in one row:
                    s[np.arange(s.shape[0])[:, None], np.argpartition(s, 10, axis=1)[:, :-10]] = 0


                
                # ####### Old version: 
                # CDD should be the correlation distance decay to get the search radius
                # # in this implementation we take always k station, regardless of the radius
                # # thus we can use CDD=max(distances)
                # CDD = np.empty((len(distances),) + np.shape(z[0]))
                # CDD[dist_leq_min_upper_bound] = np.max(distances[dist_leq_min_upper_bound],axis=1)
                # # formula for weights:
                # # wi = [e^(−x/CDD)]^m 
                # # where m is fixed to 4 and x is the distance between the station i and the point 
                # m_const = 4.0 # constant
                # # initialize weights
                # weight_directional = np.zeros_like(distances)
                # # get distance weights            
                # s = np.zeros_like(distances)       
                # s[dist_leq_min_upper_bound] = np.exp(-distances[dist_leq_min_upper_bound]*m_const/CDD[dist_leq_min_upper_bound,np.newaxis])
    

            # start_time = time.time()
            if not use_broadcasting:
                weight_directional = np.zeros_like(distances)
                for i in range(nnear):
                    xj_diff = self.lat_inALL[:, np.newaxis] - self.latgrib[indexes]
                    yj_diff = self.lon_inALL[:, np.newaxis] - self.longrib[indexes]
                    
                    Dj = np.sqrt(xj_diff**2 + yj_diff**2)
                    # we could use "distances", but we are actually evaluating the cos funcion on lat and lon values, that 
                    # approximates the real angle... to use "distances" we need to operate in 3d version of the points
                    # in theory it should be OK to use the solution above, otherwise we can change it to 
                    # Di = distances[i]
                    # Dj = distances
                    # and formula cos_theta = [(x-xi)*(x-xj) + (y-yi)*(y-yj) + (z-zi)*(z-zj)] / di*dj
                                        
                    cos_theta = (xj_diff[:,i,np.newaxis] * xj_diff + yj_diff[:,i,np.newaxis] * yj_diff) / (Dj[:,i,np.newaxis] * Dj)
                    # skip when i==j, so that directional weight of i is evaluated on all points j where j!=i 
                    # TODO: tip: since cos_theta = 1 for i==j, to speed up we can skip this passage and apply i!=j only on denominator
                    cos_theta = cos_theta[:,np.concatenate([np.arange(i), np.arange(i+1, cos_theta.shape[1])])]
                    sj = s[:,np.concatenate([np.arange(i), np.arange(i+1, s.shape[1])])]            
                    numerator = np.sum((1 - cos_theta) * sj, axis=1)
                    denominator = np.sum(sj, axis=1)
                    weight_directional[:,i] = numerator / denominator

                    # DEBUG: test the point at n_debug 11805340=lat 8.025 lon 47.0249999
                    if DEBUG_ADW_INTERPOLATION:
                        print("i: {}".format(i))
                        print("cos_theta: {}".format(cos_theta[n_debug]))
                        print("s: {}".format(s[n_debug]))
                        print("numerator: {}".format(numerator[n_debug]))
                        print("denominator: {}".format(denominator[n_debug]))
            else:
                # All in broadcasting:     
                start = time.time()
                weight_directional = adw_and_cdd_compute_weights_directional_in_broadcasting(
                    s, self.latgrib, self.longrib, indexes,
                    self.lat_inALL, self.lon_inALL)
                checktime = time.time()
                stdout.write('adw_and_cdd_compute_weights_directional_in_broadcasting time (sec): {}\n'.format(checktime - start))

            # replace all the nan values with "1"
            # this is because we have NaNs when denominator is zero, that happens when only one station is considered 
            # in the angular evaluation, thus no agle is present
            weight_directional = np.nan_to_num(weight_directional, nan=1)

            # end_time = time.time()
            # elapsed_time = end_time - start_time
            # print(f"Elapsed time for computation: {elapsed_time:.6f} seconds")
            if (adw_type=='CDD'):
                w=s
                # in CDD the weight_directional should be normalized before multiply by 1+...
                # normalize weight_directional
                sums_weight_directional = np.sum(weight_directional, axis=1, keepdims=True)
                weight_directional = weight_directional / sums_weight_directional
                
            # update weights with directional ones
            if DEBUG_ADW_INTERPOLATION:
                print("weight_directional: {}".format(weight_directional[n_debug]))
                print("w (before adding angular weights): {}".format(w[n_debug]))
            w = np.multiply(w,1+weight_directional)
            if DEBUG_ADW_INTERPOLATION:
                print("w (after adding angular weights): {}".format(w[n_debug]))

            # if (adw_type=='Shepard'):
            #     # TODO: Add Gradient
            #     # for each D included in C', evaluate A and B
            #     # A = Sum{wj[(zj-zi)(xj-xi)/d(Dj,Di)^2]}/Sum(wj)
            #     # B = Sum{wj[(zj-zi)(yj-yi)/d(Dj,Di)^2]}/Sum(wj)
            #     # v = O.1[max{zi} - min{zi}] / [max{(A^2+B^2)}]^(1/2). 
            #     # Dzi = [Ai(x-xi) + Bi(y-yi)][v/(v+di)]
            #     # final results:
            #     # value = Sum[wi(zi+Dzi)] / Sum(wi) when d!=0, else zi


        elif (adw_type!=None):
            raise ApplicationException.get_exc(INVALID_INTERPOL_METHOD, 
                        f"interpolation method not supported (mode = {self.mode}, nnear = {self.nnear}, adw_type = {adw_type})")

        stdout.write('{}Building coeffs: {}/{} ({:.2f}%)\n'.format(back_char, 2, 5, 2*100/5))
        stdout.flush()
        #normalize weights
        if (adw_type=='Shepard') or (adw_type=='CDD'):
            sums = np.sum(w, axis=1, keepdims=True)
            weights = w / sums
        else:
            sums = np.sum(w[dist_leq_min_upper_bound], axis=1, keepdims=True)
            weights[dist_leq_min_upper_bound] = w[dist_leq_min_upper_bound] / sums
        if DEBUG_ADW_INTERPOLATION:
            # dist_smalltest = distances[:, 0] <= 10000
            # onlyfirst_array_test = np.zeros(nnear)
            # onlyfirst_array_test[0] = 1000
            # weights[dist_smalltest]=onlyfirst_array_test
            print("weights (after normalization): {}".format(weights[n_debug]))
        stdout.write('{}Building coeffs: {}/{} ({:.2f}%)\n'.format(back_char, 3, 5, 3*100/5))
        stdout.flush()

        wz = np.einsum('ij,ij->i', weights, z[indexes])
        stdout.write('{}Building coeffs: {}/{} ({:.2f}%)\n'.format(back_char, 4, 5, 4*100/5))
        stdout.flush()
        if (adw_type=='Shepard') or (adw_type=='CDD'):
            idxs = indexes
            result = wz
            
            if (adw_type=='Shepard'):
                # in Shepard, we still have NaN values because of the denominator when the distance is equal to 0
                # so we just take the exact value when the point is exacly on the station coordinates
                dist_leq_1e_10 = distances[:, 0] <= 1e-10
            
                # distances <= 1e-10 : take exactly the point, weight = 1
                onlyfirst_array = np.zeros(nnear, dtype=weights.dtype)
                onlyfirst_array[0] = 1
                weights[dist_leq_1e_10] = onlyfirst_array
                idxs[dist_leq_1e_10] = indexes[dist_leq_1e_10]
                result[dist_leq_1e_10] = z[indexes[dist_leq_1e_10][:, 0]]
        else:
            idxs[dist_leq_min_upper_bound] = indexes[dist_leq_min_upper_bound]
            result[dist_leq_min_upper_bound] = wz[dist_leq_min_upper_bound]
        if DEBUG_ADW_INTERPOLATION:
            print("result: {}".format(result[n_debug]))
            if adw_type is None:
                self.lat_inALL = self.target_latsOR.ravel()
                self.lon_inALL = self.target_lonsOR.ravel()

            print("lat: {}".format(self.lat_inALL[n_debug]))
            print("lon: {}".format(self.lon_inALL[n_debug]))
            # Lon 0.46648 Lat 45.31663
            # Lon 0.50048 Lat 45.31663

            print("idxs: {}".format(idxs[n_debug]))
            print("distances: {}".format(distances[n_debug]))
            print("latgrib: {}".format(self.latgrib[idxs[n_debug]]))
            print("longrib: {}".format(self.longrib[idxs[n_debug]]))
            print("value: {}".format(self.z[idxs[n_debug]]))
        stdout.write('{}Building coeffs: {}/{} (100%)\n'.format(back_char, 5, 5))
        stdout.flush()

        return result, weights, idxs

    # take additional points from the KDTree close to the current point and replace the wrong ones with a new ones
    def replaceIndex(self, indexes_to_replace, indexes, nn, additional_points):
        additional_points += len(indexes_to_replace)
        # replace the unwanted index with next one:
        _, replacement_indexes = self.tree.query(self.target_location, k=self.nnear+additional_points, workers=self.njobs) 
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
        return self.replaceIndexCloseToPoint(indexes_to_replace, 180-self.lat_in, self.lon_in, indexes, nn)

    # take additional points from the KDTree close to the another specific point
    # and replace the wrong ones with new ones
    def replaceIndexCloseToPoint(self, indexes_to_replace, new_lat, new_lon, indexes, nn):
        # replace up to 2 unwanted indexes with next ones:
        x, y, z = self.to_3d(new_lon, new_lat, to_regular=self.target_grid_is_rotated)
        new_target_location = [x,y,z]
        _, replacement_indexes = self.tree.query(new_target_location, k=len(indexes_to_replace), workers=self.njobs) 
        # print("replacement_indexes: {}".format(replacement_indexes))
        
        # get rid of the wrong points and add the farthest among the new selected points
        if len(indexes_to_replace)>1:
            for n,i in enumerate(indexes_to_replace):
                indexes[nn, indexes[nn, 0:4] == i] = replacement_indexes[-(n+1)]
        else:
            indexes[nn, indexes[nn, 0:4] == indexes_to_replace[0]] = replacement_indexes

        if len(np.unique(indexes[nn, 0:4]))!=4:
            # print("Less then 4 distinct point!")
            return False

        return True

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

        outs = 0            # number of points falling outside the min_upper_bound distance
        not_in_quad = 0     # number of points falling outside quadrilaterals after max_retries

        # max number of retry equals to a full lenght of lon coordinates
        max_retries = self.target_lonsOR.shape[0]        
        max_used_additional_points = 0
        nn_max_used_additional_points = -1

        latgrib_max = self.latgrib.max()
        latgrib_min = self.latgrib.min()
        longrib_max = self.longrib.max()
        longrib_min = self.longrib.min()
        # evaluate an approx_grib_resolution by using 10 times the first longidure values 
        # to check if the whole globe is covered
        approx_grib_resolution = abs(self.longrib[0]-self.longrib[1])*1.5
        is_global_map = (360-(longrib_max-longrib_min))<approx_grib_resolution
        # for nn in range(25898400,len(indexes)):
        for nn in range(len(indexes)):
            skip_current_point = False
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
            # if nn==25898400:
            #     print('self.lat_in = {}, self.lon_in = {}, nn = {}'.format(self.lat_in,self.lon_in,nn))
            #     if abs(self.lat_in-69.958)<0.02 and abs(self.lon_in-(-23.608))<0.02:
            #         print('self.lat_in = {}, self.lon_in = {}, nn = {}'.format(self.lat_in,self.lon_in,nn))

            # check distances 
            if dist[0] <= 1e-10:  
                result[nn] = z[ix[0]]  # take exactly the point, weight = 1
                idxs[nn] = ix
                weights[nn] = np.array([1., 0., 0., 0.])
            elif dist[0] > self.min_upper_bound:
                outs += 1
                idxs[nn] = ix
                weights[nn] = np.array([np.nan, 0., 0., 0.])
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

                    # in non-global maps, skip all points falling outside the grib min and max values
                    if is_global_map==False and \
                        (self.lat_in>latgrib_max or self.lat_in<latgrib_min or self.lon_in>longrib_max or self.lon_in<longrib_min):
                            quadrilateral_is_ok = True
                            outs += 1
                            weights[nn] = np.array([np.nan, 0., 0., 0.])
                            result[nn] = empty_array
                            skip_current_point = True

                    # check grib type (if grig is on parallels or projected (self.source_grid_is_rotated=True))
                    # in case we are not in parallel-like grib files, let's use the old bilinear method 
                    # that works with every grid but is less precise
                    # see here for possible grib files https://apps.ecmwf.int/codes/grib/format/grib1/grids/10/
                    if additional_checks_completed == False and skip_current_point == False:
                        # the grib file has different number of longitude points for each latitude,
                        # thus I will make sure to use only 2 above and two below of the current point
                        # the function will return the wrong point, if any
                        index_wrong_points = getWrongPointDirection(self.lat_in, self.lon_in, corners_points)
                        if len(index_wrong_points):
                            # check if the latitude point is above the maximum or below the minimun latitude, 
                            if self.lat_in>latgrib_max or self.lat_in<latgrib_min:
                                # to speed up the process and retrieve better "close points" from the KDTree 
                                # I will look for nearest points of the opposite side of the globe
                                if self.replaceIndexOppositeSide(index_wrong_points, indexes, nn) == False:
                                    # if there is no replacement with 4 points, get only the nearest point
                                    quadrilateral_is_ok = True
                                    outs += 1
                                    result[nn] = z[idxs[nn,0]]  # take exactly the point, weight = 1
                                    weights[nn] = np.array([1., 0., 0., 0.])
                                    skip_current_point = True

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
                    if additional_checks_completed == True and skip_current_point == False:
                        #get p1,p2,p3,p4 in clockwise order
                        self.p1, self.p2, self.p3, self.p4 = get_clockwise_points(corners_points)
                        # check for convexity
                        is_convex = isConvexQuadrilateral(self.p1[0:2], self.p2[0:2], self.p3[0:2], self.p4[0:2])
                        if self.source_grid_is_rotated:
                            # in case of rotated grid, actually the convexity check give worst results
                            # so let's just skip this check
                            is_convex = True 

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

                if skip_current_point == False:
                    if max_used_additional_points<additional_points:
                        max_used_additional_points = additional_points
                        nn_max_used_additional_points = nn
                        print("\nmax_used_additional_points: {}, nn_max_used_additional_points: {}".format(max_used_additional_points, nn_max_used_additional_points))

                    try:
                        assert(len(np.unique(indexes[nn, 0:4]))==4) 
                    except AssertionError as e:
                        ApplicationException.get_exc(WEIRD_STUFF, details=str(e) + "\nLess then 4 distinct point! nn={} lat={} lon={}".format(nn, self.lat_in, self.lon_in))
                    
                    if quadrilateral_is_ok==False:
                        #print("\nError: quadrilateral_is_ok is False, failed to find a correct quadrilateral: nn is {}, lat={} lon={}".format(nn, self.lat_in, self.lon_in))
                        not_in_quad+=1

                    [alpha, beta] = np.clip(opt.fsolve(self._functionAlphaBeta, (0.5, 0.5)), 0, 1)
                    weight1[nn] = (1-alpha)*(1-beta)
                    weight2[nn] = alpha*(1-beta)
                    weight3[nn] = alpha*beta
                    weight4[nn] = (1-alpha)*beta

                    weights[nn, 0:4] = np.array([weight1[nn], weight2[nn], weight3[nn], weight4[nn]])
                    idxs[nn, 0:4] = np.array([self.p1[3], self.p2[3], self.p3[3], self.p4[3]])
                    result[nn] = weight1[nn]*self.p1[2] + weight2[nn]*self.p2[2] + weight3[nn] * self.p3[2] + weight4[nn] * self.p4[2]  

        stdout.write('{}{:>100}'.format(back_char, ' '))
        stdout.write('{}Building coeffs: {}/{} [outs: {}, not_in_quad: {}] (100%)\n'.format(back_char, num_cells, num_cells, outs, not_in_quad))
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

    def _build_weights_triangulation(self, use_bilinear = False):
        # The interpolant is constructed by triangulating the input data with Qhull, 
        # and on each triangle performing linear barycentric interpolation
        # in the same way of the function LinearNDInterpolator, 
        # but generating intertable like others pygtp interpolating functions
        nnear = self.nnear

        stdout.write('Finding Delaunay triangles for {} interpolation k={}\n'.format(self.mode, self.nnear))

        normalized_latgrib=self.latgrib.copy()
        normalized_longrib=self.longrib.copy()
        normalized_longrib[normalized_longrib>180]-=360
        z=self.z.copy()

        longrib_max = normalized_longrib.max()
        longrib_min = normalized_longrib.min()
        # evaluate an approx_grib_resolution by using 10 times the first longitude values 
        # to check if the whole globe is covered
        approx_grib_resolution = abs(normalized_longrib[0]-normalized_longrib[1])*1.5
        is_global_map = (360-(longrib_max-longrib_min))<approx_grib_resolution
        if is_global_map:
            #additional points map
            original_indexes=[]
            original_indexes = np.append(original_indexes,np.where(normalized_longrib>longrib_max-approx_grib_resolution*2)).astype(int)
            original_indexes = np.append(original_indexes,np.where(normalized_longrib<longrib_min+approx_grib_resolution*2)).astype(int)
            # add values on left and right borders taking them from the opposite direction
            padded_longrib = np.append(normalized_longrib,normalized_longrib[normalized_longrib>longrib_max-approx_grib_resolution*2]-360)
            padded_latgrib = np.append(normalized_latgrib,normalized_latgrib[normalized_longrib>longrib_max-approx_grib_resolution*2])
            padded_z = np.append(z,z[normalized_longrib>longrib_max-approx_grib_resolution*2])
            padded_longrib = np.append(padded_longrib,normalized_longrib[normalized_longrib<longrib_min+approx_grib_resolution*2]+360)
            padded_latgrib = np.append(padded_latgrib,normalized_latgrib[normalized_longrib<longrib_min+approx_grib_resolution*2])
            padded_z = np.append(padded_z,z[normalized_longrib<longrib_min+approx_grib_resolution*2])
            normalized_longrib = padded_longrib
            normalized_latgrib = padded_latgrib
            z=padded_z
        else:
            stdout.write('Finding nearest neighbor to exclude outside triangles\n')
            x_tmp, y_tmp, z_tmp = self.to_3d(self.target_lonsOR[:,:], self.target_latsOR[:,:], to_regular=self.target_grid_is_rotated)
            efas_locations = np.vstack((x_tmp.ravel(), y_tmp.ravel(), z_tmp.ravel())).T
            distances, _ = self.tree.query(efas_locations, k=1, workers=self.njobs) 

        gribpoints = np.stack((normalized_latgrib,normalized_longrib),axis=-1)
        gribpoints_scaled = gribpoints.copy()
        # In case of non rotated grib files, the grid has variable number of points according to the latitude, 
        # so adjust the grid spaces for an effective triangulation
        # In case of rotated grid, instead, use the original grid points, that is fine for the spece even if it is rotaded
        if self.source_grid_is_rotated == False:
            for i in range(gribpoints_scaled.shape[0]):
                gribpoints_scaled[i,0], error = quad(integrand, 0, np.radians(gribpoints_scaled[i,0]))

            gribpoints_scaled[:,0] = gribpoints_scaled[:,0]*90*10/max(gribpoints_scaled[:,0])

        tri = Delaunay(gribpoints_scaled)        
        #tri = Delaunay(gribpoints)
        p = np.stack((self.target_latsOR[:,:].ravel(),self.target_lonsOR[:,:].ravel()),axis=-1)
        target_latsORscaled = self.target_latsOR[:,0].copy()
        # In case of non rotated grib files, the grid has variable number of points according to the latitude, 
        # so adjust the grid spaces for an effective triangulation
        # In case of rotated grid, instead, use the original grid points, that is fine for the spece even if it is rotaded
        if self.source_grid_is_rotated == False:
            for i in range(target_latsORscaled[:].shape[0]):
                target_latsORscaled[i], error = quad(integrand, 0, np.radians(target_latsORscaled[i]))
            target_latsORscaled[:] = target_latsORscaled[:]*90*10/max(quad(integrand, 0, np.radians(max(gribpoints[:,0]))))
        
        target_latsORscaled = np.ones((1, self.target_latsOR.shape[1])) * target_latsORscaled.reshape(-1,1)
        p_scaled = np.stack((target_latsORscaled.ravel(),self.target_lonsOR[:,:].ravel()),axis=-1)

        result = mask_it(np.empty((p.shape[0],) +
                         np.shape(z[0])), self._mv_target, 1)
        weights = np.empty((p.shape[0],) + (nnear,))

        # plt.triplot(gribpoints[:,0], gribpoints[:,1], tri.simplices)
        # plt.plot(gribpoints[:,0], gribpoints[:,1], 'o')
        # # plt.plot(p[:,0], p[:,1], 'x')
        # plt.show()

        # store in idxs_tri the nr of triangle of the grib in which each p is in, from p[0] to p[max]
        idxs_tri=tri.find_simplex(p_scaled)  
        #idxs contains the indexes of the grib vertex of the triagles that contain p
        # e.g. idxs[nn] contains the indexes of the grib vertex containing p[nn]
        idxs = tri.simplices[idxs_tri]
        outs = 0
        empty_array = empty(z[0].shape, self._mv_target)
        num_cells = result.size
        back_char, progress_step = progress_step_and_backchar(num_cells)
        stdout.write('{}Building coeffs: 0/{} [outs: 0] (0%)'.format(back_char, num_cells))
        stdout.flush()

        numbi=0
        numtri=0

        if use_bilinear:
            # add the fourth point to each idxs[nn] from the near triangle on the longest side
            idxs = np.column_stack((idxs,empty(idxs.shape[0],-1,dtype=idxs.dtype)))
            idxs_tri_neighbors = tri.neighbors[idxs_tri]
            idxs_tri_neighbors_to_use = empty(idxs_tri_neighbors.max()+1,-1,dtype=idxs_tri.dtype)

        for nn in range(len(idxs_tri)):
            if nn % progress_step == 0:
                stdout.write('{}Building coeffs: {}/{} [outs: {}] ({:.2f}%)'.format(back_char, nn, num_cells, outs, nn * 100. / num_cells))
                stdout.flush()
            # Here, skip points that are not in triangles, or that are in triangles having a side > min_upper_bound in global maps.
            # In non-global maps, skip all points falling outside the grib values using nearest neighbor method
            if (idxs_tri[nn]==-1) or \
                (is_global_map==False and distances[nn] > self.min_upper_bound):
                outs += 1
                weights[nn] = empty(z[0].shape)
                result[nn] = empty_array
            else:
                # evaluate the location of vertex and exclude triangles with very far vertex
                x_tmp, y_tmp, z_tmp = self.to_3d(normalized_longrib[idxs[nn]], normalized_latgrib[idxs[nn]], to_regular=not self.rotated_bugfix_gribapi)
                vertex_locations = np.vstack((x_tmp.ravel(), y_tmp.ravel(), z_tmp.ravel())).T
                if (is_global_map==False) and \
                    ((np.linalg.norm(vertex_locations[0] - vertex_locations[1]) > self.min_upper_bound*10) or \
                    (np.linalg.norm(vertex_locations[1] - vertex_locations[2]) > self.min_upper_bound*10) or \
                    (np.linalg.norm(vertex_locations[0] - vertex_locations[2]) > self.min_upper_bound*10)):
                    outs += 1
                    weights[nn] = empty(z[0].shape)
                    result[nn] = empty_array
                else:
                    if use_bilinear:
                        # In case of bilinear interpolation, when possible, use the neighbor triangle to form a quadrilateral.
                        # As neighbor to use, take the triangle on the longest side (opposite to the widest angle)
                        angles=np.zeros(3)
                        angles[0]=get_angle(gribpoints_scaled[idxs[nn,2]], gribpoints_scaled[idxs[nn,0]], gribpoints_scaled[idxs[nn,1]])
                        if angles[0]>180:
                            angles[0] = 360 - angles[0] 
                        if angles[0]>=90:
                            idx_to_use = 0
                        else:
                            angles[1]=get_angle(gribpoints_scaled[idxs[nn,0]], gribpoints_scaled[idxs[nn,1]], gribpoints_scaled[idxs[nn,2]])
                            if angles[1]>180:
                                angles[1] = 360 - angles[1] 
                            angles[2]=180-angles[0]-angles[1]
                            idx_to_use = np.argmax(angles)
                        if idxs_tri_neighbors[nn,idx_to_use]>-1:
                            if idxs_tri_neighbors_to_use[idxs_tri[nn]] == -1 and idxs_tri_neighbors_to_use[idxs_tri_neighbors[nn,idx_to_use]] == -1:
                                idxs_tri_neighbors_to_use[idxs_tri[nn]] = idxs_tri_neighbors[nn,idx_to_use]
                                idxs_tri_neighbors_to_use[idxs_tri_neighbors[nn,idx_to_use]] = idxs_tri[nn]
                        if idxs_tri_neighbors_to_use[idxs_tri[nn]]>-1:
                            idxs[nn]=np.unique(np.append(idxs[nn,0:3],tri.simplices[idxs_tri_neighbors_to_use[idxs_tri[nn]]]))
                    
                    if len(idxs[nn][idxs[nn]>=0])==4:
                        self.lat_in, self.lon_in = p[nn]
                        lats = normalized_latgrib[idxs[nn]]
                        lons = normalized_longrib[idxs[nn]]

                        corners_points = np.array([[lats[0], lons[0], z[idxs[nn,0]], idxs[nn,0]],
                            [lats[1], lons[1], z[idxs[nn,1]], idxs[nn,1]],
                            [lats[2], lons[2], z[idxs[nn,2]], idxs[nn,2]],
                            [lats[3], lons[3], z[idxs[nn,3]], idxs[nn,3]]])
                        self.p1, self.p2, self.p3, self.p4 = get_clockwise_points(corners_points)
                        [alpha, beta] = np.clip(opt.fsolve(self._functionAlphaBeta, (0.5, 0.5)), 0, 1)
                        weight1 = (1-alpha)*(1-beta)
                        weight2 = alpha*(1-beta)
                        weight3 = alpha*beta
                        weight4 = (1-alpha)*beta

                        weights[nn, 0:4] = np.array([weight1, weight2, weight3, weight4])
                        idxs[nn, 0:4] = np.array([self.p1[3], self.p2[3], self.p3[3], self.p4[3]])
                        result[nn] = weight1*self.p1[2] + weight2*self.p2[2] + weight3 * self.p3[2] + weight4 * self.p4[2]                          
                        numbi+=1
                    else:
                        numtri+=1
                        b = tri.transform[idxs_tri[nn],:2].dot(np.transpose(p_scaled[nn] - tri.transform[idxs_tri[nn],2]))
                        weights[nn] = np.append(np.append(np.transpose(b),1 - b.sum(axis=0)),np.zeros(nnear-3))
                        result[nn] = weights[nn,0]*z[idxs[nn,0]] + weights[nn,1]*z[idxs[nn,1]] + weights[nn,2]*z[idxs[nn,2]]
        if (is_global_map==True):
            idxs[idxs>len(self.latgrib)]=original_indexes[idxs[idxs>len(self.latgrib)]-len(self.latgrib)]
        stdout.write('{}{:>100}'.format(back_char, ' '))
        stdout.write('{}Building coeffs: {}/{} [outs: {}] (100%)\n'.format(back_char, num_cells, num_cells, outs))
        if use_bilinear:
            stdout.write('{}Num Bilinear interpolated points: {}, Num triangle barycentric interpolated points: {}\n'.format(back_char, numbi, numtri))
        stdout.flush()

        return result, weights, idxs
