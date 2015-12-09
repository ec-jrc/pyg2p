from sys import stdout

import gribapi
import numpy as np

from . import progress_step_and_backchar


def grib_nearest(gid, target_lats, target_lons, mv, result):

    xs = []
    ys = []
    idxs = []
    # avoid re-evaluating append methods at each loop
    x_append = xs.append
    y_append = ys.append
    idx_append = idxs.append
    flush = stdout.flush
    write_to_console = stdout.write
    i = 0
    num_cells = result.size
    back_char, progress_step = progress_step_and_backchar(num_cells)

    write_to_console('{}Interpolation progress: 0/{} [out:0] (0%)'.format(back_char, num_cells))
    flush()
    outs = 0
    for (x, y), val in np.ndenumerate(target_lons):
        i += 1
        if not target_lons[x, y] == mv and not target_lons[x, y] <= -1.0e+10:
            if i % progress_step == 0:
                write_to_console('{}Interpolation progress: {}/{} [out:{}] ({:.2f}%)'.format(back_char, i, num_cells, outs, i * 100. / num_cells))
                flush()
            try:
                # import ipdb
                # ipdb.set_trace()
                n_nearest = gribapi.grib_find_nearest(gid, np.asscalar(target_lats[x, y]), np.asscalar(target_lons[x, y]))
                x_append(x)
                y_append(y)
                idx_append(n_nearest[0]['index'])
            except gribapi.GribInternalError as e:
                outs += 1
    write_to_console('{}{}'.format(back_char, ' ' * 100))
    write_to_console('{}Interpolation progress: {}/{}  [out of grid:{}] (100%)\n'.format(back_char, i, num_cells, outs))
    flush()
    return np.asarray(xs), np.asarray(ys), np.asarray(idxs)


def grib_invdist(gid, target_lats, target_lons, mv, result):
    xs = []
    ys = []
    idxs1 = []
    idxs2 = []
    idxs3 = []
    idxs4 = []
    coeffs1 = []
    coeffs2 = []
    coeffs3 = []
    coeffs4 = []
    # avoid re-evaluating methods at each loop
    x_append = xs.append
    y_append = ys.append
    idx1_append = idxs1.append
    idx2_append = idxs1.append
    idx3_append = idxs1.append
    idx4_append = idxs1.append
    coeff1_append = coeffs1.append
    coeff2_append = coeffs1.append
    coeff3_append = coeffs1.append
    coeff4_append = coeffs1.append
    flush = stdout.flush
    write_to_console = stdout.write

    i = 0
    num_cells = result.size
    back_char, progress_step = progress_step_and_backchar(num_cells)
    write_to_console('{}Interpolation progress: 0/{} [out:0] (0%)'.format(back_char, num_cells))
    flush()
    outs = 0
    for (x, y), valuesgg in np.ndenumerate(target_lons):
        i += 1
        if not target_lons[x, y] == mv and not target_lons[x, y] < -1.0e+10:
            if i % progress_step == 0:
                write_to_console('{}Interpolation progress: {}/{} [out:{}] ({:.2f}%)'.format(back_char, i, num_cells, outs, i * 100. / num_cells))
                flush()
            try:
                exact_position = False
                n_nearest = gribapi.grib_find_nearest(gid, np.asscalar(target_lats[x, y]), np.asscalar(target_lons[x, y]), npoints=4)
                x_append(x)
                y_append(y)
                for ig in xrange(4):
                    if n_nearest[ig]['distance'] == 0:
                        exact_position = True
                        exact_position_idx = ig
                        break

                inv1 = (1 / n_nearest[0]['distance']) if not exact_position else 1
                inv2 = (1 / n_nearest[1]['distance']) if not exact_position else 0
                inv3 = (1 / n_nearest[2]['distance']) if not exact_position else 0
                inv4 = (1 / n_nearest[3]['distance']) if not exact_position else 0
                idx1_append(n_nearest[0]['index'] if not exact_position else n_nearest[exact_position_idx]['index'])
                idx2_append(n_nearest[1]['index'] if not exact_position else 0)
                idx3_append(n_nearest[2]['index'] if not exact_position else 0)
                idx4_append(n_nearest[3]['index'] if not exact_position else 0)

                sums = inv1 + inv2 + inv3 + inv4
                coeff1 = inv1 / sums
                coeff2 = inv2 / sums
                coeff3 = inv3 / sums
                coeff4 = inv4 / sums
                coeff1_append(coeff1)
                coeff2_append(coeff2)
                coeff3_append(coeff3)
                coeff4_append(coeff4)

            except gribapi.GribInternalError:
                # tipically "out of grid" error
                outs += 1
    write_to_console('{}{}'.format(back_char, ' ' * 100))
    write_to_console('{}Interpolation progress: {}/{}  [out of grid:{}] (100%)\n'.format(back_char, i, num_cells, outs))
    flush()
    return np.asarray(xs), np.asarray(ys), \
        np.asarray(idxs1), np.asarray(idxs2), np.asarray(idxs3), np.asarray(idxs4), \
        np.asarray(coeffs1), np.asarray(coeffs2), np.asarray(coeffs3), np.asarray(coeffs4)
