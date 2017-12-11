import numpy as np
from numpy import ma

int_fill_value = -999999


def mask_it(v, mv, shape=None):
    if shape is not None:
        result = np.ma.masked_array(data=v, fill_value=mv, copy=False)
    else:
        result = np.ma.masked_values(v, mv, copy=False)
    return result


def empty(shape, fill_value=np.NaN, dtype=float):
    idxs = np.empty(shape, dtype=dtype)
    idxs.fill(fill_value)
    return idxs


def result_masked(values, fill_value):
    if not isinstance(values, ma.core.MaskedArray):
        return values
    # handling a masked array
    masked_out = ma.masked_where(values.mask, values.data, copy=False)
    masked_out = ma.filled(masked_out, fill_value)
    return masked_out


def get_masks(*args):
    mask = None
    for num_array in args:
        if not isinstance(num_array, ma.core.MaskedArray):
            continue
        mask = num_array.mask if mask is None else mask | num_array.mask
    return mask
