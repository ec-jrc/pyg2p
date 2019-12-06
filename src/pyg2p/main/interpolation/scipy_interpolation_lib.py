from math import radians
from sys import stdout

import eccodes
import numexpr as ne
import numpy as np
from scipy.spatial import cKDTree as KDTree

from ..exceptions import ApplicationException, WEIRD_STUFF
from pyg2p.util.numeric import mask_it, empty
from pyg2p.util.generics import progress_step_and_backchar
from pyg2p.util.strings import now_string


class InverseDistance(object):
    """
    http://docs.scipy.org/doc/scipy/reference/spatial.html
    """
    gribapi_version = list(map(int, eccodes.codes_get_api_version().split('.')))
    rotated_bugfix_gribapi = gribapi_version[0] > 1 or (gribapi_version[0] == 1 and gribapi_version[1] > 14) or (gribapi_version[0] == 1 and gribapi_version[1] == 14 and gribapi_version[2] >= 3)

    def __init__(self, longrib, latgrib, grid_details, source_values, nnear, mv_target, mv_source, target_is_rotated=False, parallel=False):
        stdout.write('Start scipy interpolation: {}\n'.format(now_string()))
        self.geodetic_info = grid_details
        self.source_grid_is_rotated = 'rotated' in grid_details.get('gridType')
        self.target_grid_is_rotated = target_is_rotated
        self.njobs = 1 if not parallel else -1
        self.nnear = nnear
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
        x, y, z = self.to_3d(target_lons, target_lats, to_regular=self.target_grid_is_rotated)
        efas_locations = np.vstack((x.ravel(), y.ravel(), z.ravel())).T

        stdout.write('Finding indexes for nearest neighbour k={}\n'.format(self.nnear))

        distances, indexes = self.tree.query(efas_locations, k=self.nnear, n_jobs=self.njobs)

        if self.nnear == 1:
            # return distances, distances, indexes
            result, indexes = self._build_nn(distances, indexes)
            weights = distances
        else:
            # return distances, distances, indexes
            result, weights, indexes = self._build_weights(distances, indexes, self.nnear)

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

    def _build_weights(self, distances, indexes, nnear):
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
