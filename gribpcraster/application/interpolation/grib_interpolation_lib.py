from sys import stdout

import gribapi
import numpy as np

from gribpcraster.application.interpolation import progress_step_and_backchar


def _grib_nearest(gid, target_lats, target_lons, mv, result):

    xs = []
    ys = []
    idxs = []
    i = 0
    num_cells = result.size
    back_char, progress_step = progress_step_and_backchar(num_cells)

    stdout.write(back_char + 'Interpolation progress: %d/%d (%d%%)' % (0, num_cells, 0))
    stdout.flush()
    outs = 0
    for (x, y), val in np.ndenumerate(target_lons):
        i += 1
        if not target_lons[x, y] == mv and not target_lons[x, y] <= -1.0e+10:
            if i % progress_step == 0:
                stdout.write(back_char + 'Interpolation progress: %d/%d [out:%d] (%.2f%%)' % (i, num_cells, outs,i*100./num_cells))
                stdout.flush()
            try:
                n_nearest = gribapi.grib_find_nearest(gid, np.asscalar(target_lats[x, y]), np.asscalar(target_lons[x, y]))
                xs.append(x)
                ys.append(y)
                idxs.append(n_nearest[0]['index'])
            except gribapi.GribInternalError:
                outs += 1
    stdout.write(back_char + ' ' * 100)
    stdout.write(back_char + 'Interpolation progress: %d/%d (%.2f%%)\n' % (i, num_cells, 100))
    stdout.flush()
    return np.asarray(xs), np.asarray(ys), np.asarray(idxs)


def _grib_invdist(gid, target_lats, target_lons, mv, result):
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
    i = 0
    num_cells = result.size
    back_char, progress_step = progress_step_and_backchar(num_cells)
    stdout.write(back_char + 'Interpolation progress: %d/%d (%d%%)' % (0, num_cells, 0))
    stdout.flush()
    out = 0
    for (x, y), valuesgg in np.ndenumerate(target_lons):
        i += 1
        if not target_lons[x, y] == mv and not target_lons[x, y] < -1.0e+10:
            if i % progress_step == 0:
                stdout.write(back_char + 'Interpolation progress: %d/%d [out:%d] (%.2f%%)' % (i, num_cells, out, i * 100. / num_cells))
                stdout.flush()
            try:
                notExactPosition = True
                n_nearest = gribapi.grib_find_nearest(gid, np.asscalar(target_lats[x, y]), np.asscalar(target_lons[x, y]), npoints=4)
                xs.append(x)
                ys.append(y)
                for ig in range(4):
                    if n_nearest[ig]['distance'] == 0:
                        notExactPosition = False
                        exactPositionIdx = ig
                        break

                inv1 = (1 / n_nearest[0]['distance']) if notExactPosition else 1
                inv2 = (1 / n_nearest[1]['distance']) if notExactPosition else 0
                inv3 = (1 / n_nearest[2]['distance']) if notExactPosition else 0
                inv4 = (1 / n_nearest[3]['distance']) if notExactPosition else 0
                idxs1.append(n_nearest[0]['index'] if notExactPosition else n_nearest[exactPositionIdx]['index'])
                idxs2.append(n_nearest[1]['index'] if notExactPosition else 0)
                idxs3.append(n_nearest[2]['index'] if notExactPosition else 0)
                idxs4.append(n_nearest[3]['index'] if notExactPosition else 0)

                sums = inv1 + inv2 + inv3 + inv4
                coeff1 = inv1 / sums
                coeff2 = inv2 / sums
                coeff3 = inv3 / sums
                coeff4 = inv4 / sums
                coeffs1.append(coeff1)
                coeffs2.append(coeff2)
                coeffs3.append(coeff3)
                coeffs4.append(coeff4)

            except gribapi.GribInternalError:
                # tipically "out of grid" error
                out += 1
    stdout.write(back_char + ' ' * 100)
    stdout.write(back_char + 'Interpolation progress: %d/%d (%.2f%%)\n' % (i, num_cells, 100))
    stdout.flush()
    return np.asarray(xs), np.asarray(ys), np.asarray(idxs1),np.asarray(idxs2),np.asarray(idxs3),np.asarray(idxs4),np.asarray(coeffs1),np.asarray(coeffs2),np.asarray(coeffs3),np.asarray(coeffs4)