import numpy as np

__author__ = 'dominik'


def _mask_it(v, mv, shape=None):
    if shape is not None:
        result = v
        #result.fill(mv)
        result = np.ma.masked_array(data=result, fill_value=mv)
    else:
        result = np.ma.masked_values(v, mv)
    return result