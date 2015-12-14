"""
Grib interpolation utils.
For global target grids it takes two days on Intel(R) Core(TM) i7-3610QM CPU @ 2.30GHz
"""

from __future__ import division

import itertools
from sys import stdout

import gribapi
import numexpr as ne
import numpy as np

from util.generics import progress_step_and_backchar
from util.numeric import empty, int_fill_value


# TODO: Parallelize in chunks of target coordinates and merge xs, ys, idxs. Try Dask!!!


def grib_nearest(gid, target_lats, target_lons, mv):
    num_cells = target_lons.size
    indices = np.indices(target_lons.shape)
    valid_target_coords = (target_lons > -1.0e+10) & (target_lons != mv)
    xs = np.where(valid_target_coords, indices[0], int_fill_value).ravel()
    ys = np.where(valid_target_coords, indices[1], int_fill_value).ravel()
    idxs = empty(num_cells, fill_value=int_fill_value, dtype=int)

    flush = stdout.flush
    write_to_console = stdout.write
    back_char, progress_step = progress_step_and_backchar(num_cells)

    write_to_console('{}Nearest neighbour interpolation: 0/{} [out:0] (0%)'.format(back_char, num_cells))
    flush()

    i = 0
    outs = 0
    for lat, lon in itertools.izip(target_lats.flat, target_lons.flat):
        if i % progress_step == 0:
            write_to_console('{}Nearest neighbour interpolation: {}/{} [out:{}] ({:.2f}%)'.format(back_char, i, num_cells, outs, i * 100. / num_cells))
            flush()
        if not (lon <= -1.0e+10 or lon == mv):
            try:
                # TODO CHECK IF asscalar is really needed here
                n_nearest = gribapi.grib_find_nearest(gid, np.asscalar(lat), np.asscalar(lon))
            except gribapi.GribInternalError:
                outs += 1
                xs[i] = int_fill_value
                ys[i] = int_fill_value
            else:
                idxs[i] = n_nearest[0]['index']
        i += 1
    write_to_console('{}{}'.format(back_char, ' ' * 100))
    write_to_console('{}Nearest neighbour interpolation: {}/{}  [out of grid:{}] (100%)\n'.format(back_char, i, num_cells, outs))
    flush()
    return xs[xs != int_fill_value], ys[ys != int_fill_value], idxs[idxs != int_fill_value]


def grib_invdist(gid, target_lats, target_lons, mv):
    num_cells = target_lons.size
    indices = np.indices(target_lons.shape)
    valid_target_coords = (target_lons > -1.0e+10) & (target_lons != mv)
    xs = np.where(valid_target_coords, indices[0], int_fill_value).ravel()
    ys = np.where(valid_target_coords, indices[1], int_fill_value).ravel()
    idxs1 = empty(num_cells, fill_value=int_fill_value, dtype=int)
    idxs2 = empty(num_cells, fill_value=int_fill_value, dtype=int)
    idxs3 = empty(num_cells, fill_value=int_fill_value, dtype=int)
    idxs4 = empty(num_cells, fill_value=int_fill_value, dtype=int)
    invs1 = empty(num_cells)
    invs2 = empty(num_cells)
    invs3 = empty(num_cells)
    invs4 = empty(num_cells)

    flush = stdout.flush
    write_to_console = stdout.write

    back_char, progress_step = progress_step_and_backchar(num_cells)
    write_to_console('{}Inverse distance interpolation: 0/{} [out:0] (0%)'.format(back_char, num_cells))
    flush()
    i = 0
    outs = 0
    for lat, lon in itertools.izip(target_lats.flat, target_lons.flat):
        if i % progress_step == 0:
            write_to_console('{}Inverse distance interpolation: {}/{} [out:{}] ({:.2f}%)'.format(back_char, i, num_cells, outs, i * 100. / num_cells))
            flush()
        if not (lon < -1.0e+10 or lon == mv):

            try:
                # TODO CHECK IF asscalar is really needed here
                n_nearest = gribapi.grib_find_nearest(gid, np.asscalar(lat), np.asscalar(lon), npoints=4)
            except gribapi.GribInternalError:
                # tipically "out of grid" error
                outs += 1
                xs[i] = int_fill_value
                ys[i] = int_fill_value
            else:
                inv1, inv2, inv3, inv4, idx1, idx2, idx3, idx4 = _compute_coeffs_and_idxs(n_nearest)
                idxs1[i] = idx1
                idxs2[i] = idx2
                idxs3[i] = idx3
                idxs4[i] = idx4
                invs1[i] = inv1
                invs2[i] = inv2
                invs3[i] = inv3
                invs4[i] = inv4
        i += 1
    invs1 = invs1[~np.isnan(invs1)]
    invs2 = invs2[~np.isnan(invs2)]
    invs3 = invs3[~np.isnan(invs3)]
    invs4 = invs4[~np.isnan(invs4)]
    sums = ne.evaluate('invs1 + invs2 + invs3 + invs4')
    coeffs1 = ne.evaluate('invs1 / sums')
    coeffs2 = ne.evaluate('invs2 / sums')
    coeffs3 = ne.evaluate('invs3 / sums')
    coeffs4 = ne.evaluate('invs4 / sums')
    write_to_console('{}{}'.format(back_char, ' ' * 100))
    write_to_console('{}Inverse distance interpolation: {}/{}  [out of grid:{}] (100%)\n'.format(back_char, i, num_cells, outs))
    flush()
    return xs[xs != int_fill_value], ys[ys != int_fill_value], \
        idxs1[idxs1 != int_fill_value], idxs2[idxs2 != int_fill_value], idxs3[idxs3 != int_fill_value], idxs4[idxs4 != int_fill_value], \
        coeffs1, coeffs2, coeffs3, coeffs4


def _compute_coeffs_and_idxs(n_nearest):
    exact_position = False
    exact_position_idx = - 1
    for ig in xrange(4):
        if n_nearest[ig]['distance'] == 0:
            exact_position = True
            exact_position_idx = ig
            break
    inv1 = (1 / n_nearest[0]['distance']) if not exact_position else 1
    inv2 = (1 / n_nearest[1]['distance']) if not exact_position else 0
    inv3 = (1 / n_nearest[2]['distance']) if not exact_position else 0
    inv4 = (1 / n_nearest[3]['distance']) if not exact_position else 0
    idx1 = n_nearest[0]['index'] if not exact_position else n_nearest[exact_position_idx]['index']
    idx2 = n_nearest[1]['index'] if not exact_position else 0
    idx3 = n_nearest[2]['index'] if not exact_position else 0
    idx4 = n_nearest[3]['index'] if not exact_position else 0
    return inv1, inv2, inv3, inv4, idx1, idx2, idx3, idx4
