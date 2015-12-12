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

    def __init__(self, longrib, latgrib, radius, source_values, mv_target, mv_source):

        self._radius = radius
        x, y, zz = self.to_3d(longrib, latgrib)
        source_locations = np.vstack((x.ravel(), y.ravel(), zz.ravel())).T
        try:
            assert len(source_locations) == len(source_values), "len(coordinates) {} != len(values) {}".format(len(source_locations), len(source_values))
        except AssertionError as e:
            ApplicationException.get_programmatic_exc(WEIRD_STUFF, details=str(e))
        self._mv_target = mv_target
        self._mv_source = mv_source
        self.tree = KDTree(source_locations)  # build the tree
        self.z = source_values

    def to_3d(self, lons, lats):
        r = self._radius
        lons = np.radians(lons)
        lats = np.radians(lats)
        x = ne.evaluate('r * cos(lons) * cos(lats)')
        y = ne.evaluate('r * sin(lons) * cos(lats)')
        z = ne.evaluate('r * sin(lats)')
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
        weights = np.empty((len(distances),) + (nnear,))
        for dist, ix in zip(distances, indexes):
            if jinterpol % progress_step == 0:
                stdout.write('{}Inverse distance interpolation (scipy): {}/{} ({:.2f}%)'.format(back_char, jinterpol, num_cells, jinterpol * 100. / num_cells))
                stdout.flush()

            if dist[0] > 1e-10:
                w = ne.evaluate('1 / dist ** 2')
                w /= ne.evaluate('sum(w)')
                wz = np.dot(w, z[ix.astype(int, copy=False)])  # weighted values (result)
                weights[jinterpol] = w
            else:
                wz = z[ix[0]]  # take exactly the point, weight = 1
            result[jinterpol] = wz
            jinterpol += 1

        stdout.write(back_char + ' ' * 100)
        stdout.write('{}Inverse distance interpolation (scipy): {}/{} (100%)\n'.format(back_char, jinterpol, num_cells))
        stdout.flush()
        return result, weights

    def interpolate(self, lonefas, latefas, nnear):
        x, y, z = self.to_3d(lonefas, latefas)
        efas_locations = np.vstack((x.ravel(), y.ravel(), z.ravel())).T
        qdim = efas_locations.ndim
        # TODO CHECK if mask_it is needed
        # efas_locations_ma = mask_it(efas_locations, self._mv_target)
        if qdim == 1:
            efas_locations = np.array([efas_locations])

        distances, indexes = self.tree.query(efas_locations, k=nnear)
        if nnear == 1:
            # weights = np.empty((len(distances),) + (nnear,))
            weights = np.empty((len(distances),))  # weights are not used when nnear =  1
            result = self.z[indexes.astype(int, copy=False)]
        else:
            result, weights = self._build_weights(distances, indexes, nnear)
        return result, weights, indexes

