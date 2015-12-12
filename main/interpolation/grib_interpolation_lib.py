"""
Grib interpolation utils.
For global target grids it takes two days on Intel(R) Core(TM) i7-3610QM CPU @ 2.30GHz
"""


from sys import stdout
from operator import is_not
from functools import partial

import gribapi
import numpy as np

from util.generics import progress_step_and_backchar

# TODO: Parallelize in chunks of target coordinates and merge xs, ys, idxs.


def grib_nearest(gid, target_lats, target_lons, mv):
    num_cells = target_lons.size
    xs = [None] * num_cells
    ys = [None] * num_cells
    idxs = [None] * num_cells
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
                # x_append(x)
                # y_append(y)
                # idx_append(n_nearest[0]['index'])
        i += 1
    write_to_console('{}{}'.format(back_char, ' ' * 100))
    write_to_console('{}Nearest neighbour interpolation: {}/{}  [out of grid:{}] (100%)\n'.format(back_char, i, num_cells, outs))
    flush()
    xs = filter(partial(is_not, None), xs)
    ys = filter(partial(is_not, None), ys)
    idxs = filter(partial(is_not, None), idxs)
    return np.asarray(xs), np.asarray(ys), np.asarray(idxs)


def grib_invdist(gid, target_lats, target_lons, mv):
    num_cells = target_lats.size
    xs = [None] * num_cells
    ys = [None] * num_cells
    idxs1 = [None] * num_cells
    idxs2 = [None] * num_cells
    idxs3 = [None] * num_cells
    idxs4 = [None] * num_cells
    coeffs1 = [None] * num_cells
    coeffs2 = [None] * num_cells
    coeffs3 = [None] * num_cells
    coeffs4 = [None] * num_cells

    # xs = []
    # ys = []
    # idxs1 = []
    # idxs2 = []
    # idxs3 = []
    # idxs4 = []
    # coeffs1 = []
    # coeffs2 = []
    # coeffs3 = []
    # coeffs4 = []
    # avoid re-evaluating methods at each loop
    # x_append = xs.append
    # y_append = ys.append
    # idx1_append = idxs1.append
    # idx2_append = idxs2.append
    # idx3_append = idxs3.append
    # idx4_append = idxs4.append
    # coeff1_append = coeffs1.append
    # coeff2_append = coeffs2.append
    # coeff3_append = coeffs3.append
    # coeff4_append = coeffs4.append
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
    xs = filter(partial(is_not, None), xs)
    ys = filter(partial(is_not, None), ys)
    idxs1 = filter(partial(is_not, None), idxs1)
    idxs2 = filter(partial(is_not, None), idxs2)
    idxs3 = filter(partial(is_not, None), idxs3)
    idxs4 = filter(partial(is_not, None), idxs4)
    coeffs1 = filter(partial(is_not, None), coeffs1)
    coeffs2 = filter(partial(is_not, None), coeffs2)
    coeffs3 = filter(partial(is_not, None), coeffs3)
    coeffs4 = filter(partial(is_not, None), coeffs4)
    return np.asarray(xs), np.asarray(ys), \
        np.asarray(idxs1), np.asarray(idxs2), np.asarray(idxs3), np.asarray(idxs4), \
        np.asarray(coeffs1), np.asarray(coeffs2), np.asarray(coeffs3), np.asarray(coeffs4)


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
