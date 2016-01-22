import numpy as np

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
