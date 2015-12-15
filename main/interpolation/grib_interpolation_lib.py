"""
Grib interpolation utils.
For global target grids it takes two days on Intel(R) Core(TM) i7-3610QM CPU @ 2.30GHz
"""

from __future__ import division
import warnings
from functools import partial
import itertools
from sys import stdout

import numexpr as ne
import numpy as np
import gribapi
from dask import bag
from dask.diagnostics import ProgressBar

from util.generics import progress_step_and_backchar, now_string
from util.numeric import empty, int_fill_value

warnings.simplefilter(action='ignore', category=FutureWarning)


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
    write_to_console('Start interpolation: {}\n'.format(now_string()))
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
    write_to_console('End interpolation: {}\n\n'.format(now_string()))
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
    write_to_console('Start interpolation: {}\n'.format(now_string()))
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
                invs1[i], invs2[i], invs3[i], invs4[i], idxs1[i], idxs2[i], idxs3[i], idxs4[i] = _compute_coeffs_and_idxs(n_nearest)
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
    write_to_console('End interpolation: {}\n\n'.format(now_string()))
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


# Pallel version of grib api nearest neighbour


def apply_nearest_to_chunk(chunk, gid=None, mv=None):
    return np.apply_along_axis(nearest_parallel_step, 0, chunk, gid, mv)


def nearest_parallel_step(chunk, gid, mv):
    lat, lon, x, y = chunk

    idx = int_fill_value
    if not (lon <= -1.0e+10 or lon == mv):
        try:
            n_nearest = gribapi.grib_find_nearest(gid, np.asscalar(lat), np.asscalar(lon))
        except gribapi.GribInternalError:
            x = int_fill_value
            y = int_fill_value
        else:
            idx = n_nearest[0]['index']
    return int(x), int(y), idx


def grib_nearest_parallel(gid, target_lats, target_lons, mv):
    nchunks = target_lats.shape[0]
    apply_to_chunk_part = partial(apply_nearest_to_chunk, gid=gid, mv=mv)
    result = init_parallel(apply_to_chunk_part, mv, nchunks, target_lats, target_lons)
    progress = ProgressBar(dt=10)
    with progress:
        result = np.concatenate(result.compute())
    xs = result[0][result[0] != int_fill_value]
    ys = result[1][result[1] != int_fill_value]
    idxs = result[2][result[2] != int_fill_value]
    return xs, ys, idxs


# Parallel version of grib api invdist


def apply_invdist_to_chunk(chunk, gid=None, mv=None):
    return np.apply_along_axis(invdist_parallel_step, 0, chunk, gid, mv)


def invdist_parallel_step(chunk, gid, mv):
    lat, lon, x, y = chunk
    idx1 = idx2 = idx3 = idx4 = int_fill_value
    inv1 = inv2 = inv3 = inv4 = np.NaN
    if not (lon < -1.0e+10 or lon == mv):
        try:
            # TODO CHECK IF asscalar is really needed here
            n_nearest = gribapi.grib_find_nearest(gid, np.asscalar(lat), np.asscalar(lon), npoints=4)
        except gribapi.GribInternalError:
            # tipically "out of grid" error
            x = int_fill_value
            y = int_fill_value
        else:
            inv1, inv2, inv3, inv4, idx1, idx2, idx3, idx4 = _compute_coeffs_and_idxs(n_nearest)
    return x, y, idx1, idx2, idx3, idx4, inv1, inv2, inv3, inv4


def grib_invdist_parallel(gid, target_lats, target_lons, mv):

    apply_to_chunk_part = partial(apply_invdist_to_chunk, gid=gid, mv=mv)
    nchunks = target_lats.shape[0]
    result = init_parallel(apply_to_chunk_part, mv, nchunks, target_lats, target_lons)

    progress = ProgressBar(dt=10)
    with progress:
        result = np.concatenate(result.compute())

    # arrays come as float from dask because stacked with coeffs
    xs = result[0].astype(int, copy=False)
    ys = result[1].astype(int, copy=False)
    idxs1 = result[2].astype(int, copy=False)
    idxs2 = result[3].astype(int, copy=False)
    idxs3 = result[4].astype(int, copy=False)
    idxs4 = result[5].astype(int, copy=False)
    invs1 = result[6][~np.isnan(result[6])]
    invs2 = result[7][~np.isnan(result[7])]
    invs3 = result[8][~np.isnan(result[8])]
    invs4 = result[9][~np.isnan(result[9])]

    sums = ne.evaluate('invs1 + invs2 + invs3 + invs4')
    coeffs1 = ne.evaluate('invs1 / sums')
    coeffs2 = ne.evaluate('invs2 / sums')
    coeffs3 = ne.evaluate('invs3 / sums')
    coeffs4 = ne.evaluate('invs4 / sums')

    xs = xs[xs != int_fill_value]
    ys = ys[ys != int_fill_value]
    idxs1 = idxs1[idxs1 != int_fill_value]
    idxs2 = idxs2[idxs2 != int_fill_value]
    idxs3 = idxs3[idxs3 != int_fill_value]
    idxs4 = idxs4[idxs4 != int_fill_value]

    return xs, ys, idxs1, idxs2, idxs3, idxs4, coeffs1, coeffs2, coeffs3, coeffs4


def init_parallel(apply_to_chunk_part, mv, nchunks, target_lats, target_lons):
    indices = np.indices(target_lons.shape)
    npartitions = max(100, int(nchunks / 10))
    valid_coords_mask = (target_lons > -1.0e+10) & (target_lons != mv)
    xs = np.where(valid_coords_mask, indices[0], int_fill_value).ravel()
    ys = np.where(valid_coords_mask, indices[1], int_fill_value).ravel()
    stack = np.stack((target_lats.flat, target_lons.flat, xs.flat, ys.flat))
    chunks = np.array_split(stack, nchunks, axis=1)
    nearest_bag = bag.from_sequence(chunks, npartitions=npartitions)
    result = nearest_bag.map(apply_to_chunk_part)
    return result
