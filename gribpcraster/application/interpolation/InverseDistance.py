from __future__ import division
from scipy.spatial import cKDTree as KDTree
from util.logger.Logger import Logger
import numpy as np
from util.numeric.numeric import _mask_it
import gribpcraster.application.ExecutionContext as ex

__author__ = 'unknown'


def interpolate_invdist(z, _mv_efas, distances, ixs, nnear, p, wsum=None, from_inter=False):

    result = _mask_it(np.empty((len(distances),) + np.shape(z[0])), _mv_efas, 1)

    if nnear == 1:
        #for nnear=1 it doesn't care at this point if indexes come from intertable
        #                                     # or were just queried from the tree
        result = z[ixs.astype(int, copy=False)]
    elif from_inter:
        result = np.einsum('ij,ij->i', distances, z[ixs.astype(int, copy=False)])
    else:
        #nnear is 8
        from sys import stdout
        jinterpol = 0
        num_cells = result.size
        stdout.write('\rInterpolation progress: %d/%d (%.2f%%)' % (jinterpol, num_cells, jinterpol * 100. / num_cells))
        stdout.flush()
        for dist, ix in zip(distances, ixs):
            if jinterpol % 1000 == 0:
                stdout.write('\rInterpolation progress: %d/%d (%.2f%%)' % (jinterpol, num_cells, jinterpol * 100. / num_cells))
                stdout.flush()
            if dist[0] > 1e-10:
                w = 1 / dist ** p
                w /= np.sum(w)  # this must be saved into intertables..not distance!
                wz = np.dot(w, z[ix.astype(int, copy=False)])  # weighted values (result)
                wsum[jinterpol] = w
                result[jinterpol] = wz
            else:
                wz = z[ix[0]]  # take exactly the point, weight = 1
                result[jinterpol] = wz
            jinterpol += 1
        stdout.write('\rInterpolation progress: %d/%d (%.2f%%)' % (jinterpol, num_cells, 100))
        stdout.write('\n')
        stdout.flush()
    return result


"""
invdisttree.py: inverse-distance-weighted interpolation using KDTree
"""

# http://docs.scipy.org/doc/scipy/reference/spatial.html

__date__ = "2010-11-09 Nov"  # weights, doc

#...............................................................................
class InverseDistance:
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

    def __init__(self, grib_locations, z, mvEfas, mvGrib, leafsize=10):
        assert len(grib_locations) == len(z), "len(coordinates) %d != len(values) %d" % (len(grib_locations), len(z))
        import gribpcraster.application.ExecutionContext as ex
        self._logger = Logger('Interpolator', loggingLevel=ex.global_logger_level)
        self._mvEfas = mvEfas
        self._mvGrib = mvGrib
        self.tree = KDTree(grib_locations, leafsize=leafsize)  # build the tree
        self.z = z
        self.wsum = None
        self.ixs = None

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def _invdst(self, eps, p, efas_locations, mode):
        if mode == 'nearest':
            self._nnear = 1
        else:
            self._nnear = 8
        self._log('Querying tree of locations...')
        self.distances, self.ixs = self.tree.query(efas_locations, k=self._nnear, eps=eps, p=p)
        self.wsum = np.empty((len(self.distances),) +(self._nnear,))
        result = interpolate_invdist(self.z, self._mvEfas, self.distances, self.ixs, self._nnear, p, self.wsum)
        return result

    def __call__(self, efas_locations, eps=0, p=1, mode='nearest'):

        qdim = efas_locations.ndim
        efasefas_locations_ma = _mask_it(efas_locations, self._mvEfas)
        if qdim == 1:
            efas_locations = np.array([efasefas_locations_ma])
        result = self._invdst(eps, p, efas_locations, mode)
        #we return dists and ix to save them
        if self._nnear == 1:
            return result, self.distances, self.ixs
        else:
            return result, self.wsum, self.ixs