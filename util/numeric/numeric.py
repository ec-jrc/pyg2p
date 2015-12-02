import numpy as np


def mask_it(v, mv, shape=None):
    if shape is not None:
        result = np.ma.masked_array(data=v, fill_value=mv, copy=False)
    else:
        result = np.ma.masked_values(v, mv, copy=False)
    return result
