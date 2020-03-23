import os
from copy import deepcopy

import pytest

from pyg2p.main.interpolation import Interpolator
from pyg2p.main.readers import GRIBReader, PCRasterReader

from tests import MockedExecutionContext, config_dict


class TestInterpolation:
    def test_interpolation_use_scipy_nearest(self):

        file = config_dict['input.file']
        reader = GRIBReader(file)
        messages = reader.select_messages(shortName='2t')
        grid_id = messages.grid_id
        missing = messages.missing_value
        ctx = MockedExecutionContext(config_dict, False)
        interpolator = Interpolator(ctx, missing)
        values_in = messages.values_first_or_single_res[messages.first_step_range]
        lats, lons = messages.latlons
        values_resampled = interpolator.interpolate_scipy(lats, lons, values_in, grid_id, messages.grid_details)
        shape_target = PCRasterReader(config_dict['interpolation.latMap']).values.shape
        assert shape_target == values_resampled.shape

    @pytest.mark.slow
    def test_interpolation_create_scipy_invdist(self):
        d = deepcopy(config_dict)
        d['interpolation.create'] = True
        d['interpolation.parallel'] = True
        d['interpolation.mode'] = 'invdist'
        file = d['input.file']
        reader = GRIBReader(file)
        messages = reader.select_messages(shortName='2t')
        grid_id = messages.grid_id
        missing = messages.missing_value
        ctx = MockedExecutionContext(d, False)
        interpolator = Interpolator(ctx, missing)
        values_in = messages.values_first_or_single_res[messages.first_step_range]
        lats, lons = messages.latlons
        values_resampled = interpolator.interpolate_scipy(lats, lons, values_in, grid_id, messages.grid_details)
        shape_target = PCRasterReader(d['interpolation.latMap']).values.shape
        assert shape_target == values_resampled.shape
        os.unlink('tests/data/tbl_pf10tp_550800_scipy_invdist.npy.gz')

    @pytest.mark.slow
    def test_interpolation_create_eccodes_nearest(self):
        d = deepcopy(config_dict)
        d['interpolation.create'] = True
        d['interpolation.parallel'] = True
        d['interpolation.mode'] = 'grib_nearest'
        file = d['input.file']
        reader = GRIBReader(file)
        messages = reader.select_messages(shortName='2t')
        grid_id = messages.grid_id
        missing = messages.missing_value
        ctx = MockedExecutionContext(d, True)
        interpolator = Interpolator(ctx, missing)
        values_in = messages.values_first_or_single_res[messages.first_step_range]
        values_resampled = interpolator.interpolate_grib(values_in, reader._selected_grbs[0], grid_id)
        shape_target = PCRasterReader(d['interpolation.latMap']).values.shape
        assert shape_target == values_resampled.shape
        os.unlink('tests/data/tbl_cos2t_550800_grib_nearest.npy.gz')
