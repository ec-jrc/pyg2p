from __future__ import division

from sys import stdout

import numexpr as ne
import numpy as np
from scipy.spatial import cKDTree as KDTree

from main.exceptions import ApplicationException, WEIRD_STUFF
from util.numeric import mask_it
from util.generics import progress_step_and_backchar

# http://docs.scipy.org/doc/scipy/reference/spatial.html


class InverseDistance(object):
    """ inverse-distance-weighted interpolation using KDTree:
invdisttree = Invdisttree( X, z )  -- data points, values
interpol = invdisttree( q, nnear=3, eps=0, p=1, weights=None, stat=0 )
    interpolates z from the 3 points nearest each query point q;
    For example, interpol[ a query point q ]
    finds the 3 data points nearest q, at distances d1 d2 d3
    and returns the IDW average of the values z1 z2 z3
        (z1/d1 + z2/d2 + z3/d3)
        / (1/d1 + 1/d2 + 1/d3)
        = .55 z1 + .27 z2 + .18 z3  for distances 1 2 3

    q may be one point, or a batch of points.
    eps: approximate nearest, dist <= (1 + eps) * true nearest
    p: use 1 / distance**p
    weights: optional multipliers for 1 / distance**p, of the same shape as q
    stat: accumulate wsum, wn for average weights

How many nearest neighbors should one take ?
a) start with 8 11 14 .. 28 in 2d 3d 4d .. 10d; see Wendel's formula
b) make 3 runs with nnear= e.g. 6 8 10, and look at the results --
    |interpol 6 - interpol 8| etc., or |f - interpol*| if you have f(q).
    I find that runtimes don't increase much at all with nnear -- ymmv.

p=1, p=2 ?
    p=2 weights nearer points more, farther points less.
    In 2d, the circles around query points have areas ~ distance**2,
    so p=2 is inverse-area weighting. For example,
        (z1/area1 + z2/area2 + z3/area3)
        / (1/area1 + 1/area2 + 1/area3)
        = .74 z1 + .18 z2 + .08 z3  for distances 1 2 3
    Similarly, in 3d, p=3 is inverse-volume weighting.

Scaling:
    if different X coordinates measure different things, Euclidean distance
    can be way off.  For example, if X0 is in the range 0 to 1
    but X1 0 to 1000, the X1 distances will swamp X0;
    rescale the data, i.e. make X0.std() ~= X1.std() .

A nice property of IDW is that it's scale-free around query points:
if I have values z1 z2 z3 from 3 points at distances d1 d2 d3,
the IDW average
    (z1/d1 + z2/d2 + z3/d3)
    / (1/d1 + 1/d2 + 1/d3)
is the same for distances 1 2 3, or 10 20 30 -- only the ratios matter.
In contrast, the commonly-used Gaussian kernel exp( - (distance/h)**2 )
is exceedingly sensitive to distance and to h.

    """

    def __init__(self, longrib, latgrib, radius, source_values, mv_target, mv_source):
        self._radius = radius
        x, y, zz = self.to_3d(longrib, latgrib, self._radius)
        grib_locations = np.vstack((x.ravel(), y.ravel(), zz.ravel())).T
        try:
            assert len(grib_locations) == len(source_values), "len(coordinates) {} != len(values) {}".format(len(grib_locations), len(source_values))
        except AssertionError as e:
            ApplicationException.get_programmatic_exc(WEIRD_STUFF, details=str(e))
        self._mv_target = mv_target
        self._mv_source = mv_source
        self.tree = KDTree(grib_locations)  # build the tree
        self.z = source_values

    @staticmethod
    def to_3d(lons, lats, r):
        lats = np.radians(lats)
        lons = np.radians(lons)
        z = ne.evaluate('r * sin(lats)')
        x = ne.evaluate('r * cos(lons) * cos(lats)')
        y = ne.evaluate('r * sin(lons) * cos(lats)')
        return x, y, z

    def _build_weights(self, distances, indexes, nnear):

        # TODO CHECK: maybe we don't need to mask here
        z = mask_it(self.z, self._mv_source)
        # no intertable found for inverse distance nnear = 8
        # TODO CHECK if we need mask here
        result = mask_it(np.empty((len(distances),) + np.shape(z[0])), self._mv_target, 1)
        jinterpol = 0
        num_cells = result.size

        back_char, progress_step = progress_step_and_backchar(num_cells)

        stdout.write('{}Inverse distance interpolation (scipy):{}/{} (0%)'.format(back_char, jinterpol, num_cells))
        stdout.flush()
        # wsum will be saved in intertable
        wsum = np.empty((len(distances),) + (nnear,))
        for dist, ix in zip(distances, indexes):
            if jinterpol % progress_step == 0:
                stdout.write('{}Inverse distance interpolation (scipy): {}/{} ({:.2f}%)'.format(back_char, jinterpol, num_cells, jinterpol * 100. / num_cells))
                stdout.flush()

            if dist[0] > 1e-10:
                w = ne.evaluate('1 / dist ** 2')
                w /= ne.evaluate('sum(w)')
                wz = np.dot(w, z[ix.astype(int, copy=False)])  # weighted values (result)
                wsum[jinterpol] = w
            else:
                wz = z[ix[0]]  # take exactly the point, weight = 1
            result[jinterpol] = wz
            jinterpol += 1

        stdout.write(back_char + ' ' * 100)
        stdout.write('{}Inverse distance interpolation (scipy): {}/{} (100%)\n'.format(back_char, jinterpol, num_cells))
        stdout.flush()
        return result, wsum

    def interpolate(self, lonefas, latefas, nnear):
        x, y, z = self.to_3d(lonefas, latefas, self._radius)
        efas_locations = np.vstack((x.ravel(), y.ravel(), z.ravel())).T
        qdim = efas_locations.ndim
        # TODO CHECK if mask_it is needed
        efas_locations_ma = mask_it(efas_locations, self._mv_target)
        if qdim == 1:
            efas_locations = np.array([efas_locations_ma])

        distances, indexes = self.tree.query(efas_locations, k=nnear)
        if nnear == 1:
            weights = np.empty((len(distances),))  # weights are not used when nnear =  1
            result = self.z[indexes.astype(int, copy=False)]
        else:
            result, weights = self._build_weights(distances, indexes, nnear)
        return result, weights, indexes

