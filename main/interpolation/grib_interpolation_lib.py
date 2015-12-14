"""
Grib interpolation utils.
For global target grids it takes two days on Intel(R) Core(TM) i7-3610QM CPU @ 2.30GHz
"""


from sys import stdout

import gribapi
import numpy as np

from util.generics import progress_step_and_backchar

# TODO: Parallelize in chunks of target coordinates and merge xs, ys, idxs. Try Dask!!!

int_fill_value = -999999


def grib_nearest(gid, target_lats, target_lons, mv):
    num_cells = target_lons.size
    xs = np.empty(num_cells, dtype=int)
    xs.fill(int_fill_value)
    ys = np.empty(num_cells, dtype=int)
    ys.fill(int_fill_value)
    idxs = np.empty(num_cells, dtype=int)
    idxs.fill(int_fill_value)
    flush = stdout.flush
    write_to_console = stdout.write

    back_char, progress_step = progress_step_and_backchar(num_cells)

    write_to_console('{}Nearest neighbour interpolation: 0/{} [out:0] (0%)'.format(back_char, num_cells))
    flush()
    i = 0
    outs = 0
    for (x, y), lon_value in np.ndenumerate(target_lons):

        if i % progress_step == 0:
            write_to_console('{}Nearest neighbour interpolation: {}/{} [out:{}] ({:.2f}%)'.format(back_char, i, num_cells, outs, i * 100. / num_cells))
            flush()
        if not (lon_value <= -1.0e+10 or lon_value == mv):
            try:
                # TODO CHECK IF asscalar is really needed here
                n_nearest = gribapi.grib_find_nearest(gid, np.asscalar(target_lats[x, y]), np.asscalar(lon_value))
            except gribapi.GribInternalError:
                outs += 1
            else:
                xs[i] = x
                ys[i] = y
                idxs[i] = n_nearest[0]['index']
        i += 1
    write_to_console('{}{}'.format(back_char, ' ' * 100))
    write_to_console('{}Nearest neighbour interpolation: {}/{}  [out of grid:{}] (100%)\n'.format(back_char, i, num_cells, outs))
    flush()
    return xs[xs != int_fill_value], ys[ys != int_fill_value], idxs[idxs != int_fill_value]


def grib_invdist(gid, target_lats, target_lons, mv):
    num_cells = target_lons.size
    xs = np.empty(num_cells, dtype=int)
    xs.fill(int_fill_value)
    ys = np.empty(num_cells, dtype=int)
    ys.fill(int_fill_value)
    idxs1 = np.empty(num_cells, dtype=int)
    idxs1.fill(int_fill_value)
    idxs2 = np.empty(num_cells, dtype=int)
    idxs2.fill(int_fill_value)
    idxs3 = np.empty(num_cells, dtype=int)
    idxs3.fill(int_fill_value)
    idxs4 = np.empty(num_cells, dtype=int)
    idxs4.fill(int_fill_value)
    coeffs1 = np.empty(num_cells)
    coeffs1.fill(np.NaN)
    coeffs2 = np.empty(num_cells)
    coeffs2.fill(np.NaN)
    coeffs3 = np.empty(num_cells)
    coeffs3.fill(np.NaN)
    coeffs4 = np.empty(num_cells)
    coeffs4.fill(np.NaN)

    flush = stdout.flush
    write_to_console = stdout.write

    back_char, progress_step = progress_step_and_backchar(num_cells)
    write_to_console('{}Inverse distance interpolation: 0/{} [out:0] (0%)'.format(back_char, num_cells))
    flush()
    i = 0
    outs = 0
    for (x, y), lon_value in np.ndenumerate(target_lons):

        if i % progress_step == 0:
            write_to_console('{}Inverse distance interpolation: {}/{} [out:{}] ({:.2f}%)'.format(back_char, i, num_cells, outs, i * 100. / num_cells))
            flush()
        if not (lon_value < -1.0e+10 or lon_value == mv):

            try:

                # TODO CHECK IF asscalar is really needed here
                n_nearest = gribapi.grib_find_nearest(gid, np.asscalar(target_lats[x, y]), np.asscalar(lon_value), npoints=4)

            except gribapi.GribInternalError:
                # tipically "out of grid" error
                outs += 1
            else:
                coeff1, coeff2, coeff3, coeff4, idx1, idx2, idx3, idx4 = _compute_coeffs_and_idxs(n_nearest)
                xs[i] = x
                ys[i] = y
                idxs1[i] = idx1
                idxs2[i] = idx2
                idxs3[i] = idx3
                idxs4[i] = idx4
                coeffs1[i] = coeff1
                coeffs2[i] = coeff2
                coeffs3[i] = coeff3
                coeffs4[i] = coeff4
            i += 1
    write_to_console('{}{}'.format(back_char, ' ' * 100))
    write_to_console('{}Inverse distance interpolation: {}/{}  [out of grid:{}] (100%)\n'.format(back_char, i, num_cells, outs))
    flush()
    return xs[xs != int_fill_value], ys[ys != int_fill_value], \
        idxs1[idxs1 != int_fill_value], idxs2[idxs2 != int_fill_value], idxs3[idxs3 != int_fill_value], idxs4[idxs4 != int_fill_value], \
        coeffs1[~np.isnan(coeffs1)], coeffs2[~np.isnan(coeffs2)], coeffs3[~np.isnan(coeffs3)], coeffs4[~np.isnan(coeffs4)]


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
    sums = inv1 + inv2 + inv3 + inv4
    coeff1 = inv1 / sums
    coeff2 = inv2 / sums
    coeff3 = inv3 / sums
    coeff4 = inv4 / sums
    idx1 = n_nearest[0]['index'] if not exact_position else n_nearest[exact_position_idx]['index']
    idx2 = n_nearest[1]['index'] if not exact_position else 0
    idx3 = n_nearest[2]['index'] if not exact_position else 0
    idx4 = n_nearest[3]['index'] if not exact_position else 0
    return coeff1, coeff2, coeff3, coeff4, idx1, idx2, idx3, idx4
