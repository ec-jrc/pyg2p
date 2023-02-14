import numpy as np

from pyg2p import Step
from pyg2p.main.manipulation.aggregator import Aggregator, INSTANTANEOUS, ACCUMULATION, AVERAGE
from pyg2p.main.readers import GRIBReader

from tests import MockedExecutionContext, config_dict


class TestAggregator:

    def test_instant(self):
        ctx = MockedExecutionContext(config_dict, False)
        grib_reader = GRIBReader(ctx.get('input.file'))
        grib_info = grib_reader.get_grib_info({'shortName': '2t'})
        aggregator = Aggregator(aggr_step=6,
                                aggr_type=INSTANTANEOUS,
                                aggr_halfweights=False,
                                input_step=grib_info.input_step,
                                step_type=grib_info.type_of_param,
                                start_step=0,
                                mv_grib=grib_info.mv,
                                end_step=24,
                                unit_time=24,
                                force_zero_array=False)
        messages = grib_reader.select_messages(shortName='2t')
        values_orig = messages.first_resolution_values()
        values = aggregator.do_manipulation(values_orig)
        assert len(values_orig) == len(values)
        keys_orig = list(values_orig.keys())
        keys_res = list(values.keys())
        assert keys_orig[0] == keys_res[0]
        assert keys_orig[-1] == keys_res[-1]

    def test_average(self):
        ctx = MockedExecutionContext(config_dict, False)
        grib_reader = GRIBReader(ctx.get('input.file'))
        grib_info = grib_reader.get_grib_info({'shortName': '2t'})
        aggregator = Aggregator(aggr_step=24,
                                aggr_type=AVERAGE,
                                aggr_halfweights=False,
                                input_step=grib_info.input_step,
                                step_type=grib_info.type_of_param,
                                start_step=0,
                                mv_grib=grib_info.mv,
                                end_step=24,
                                unit_time=24,
                                force_zero_array=False)
        messages = grib_reader.select_messages(shortName='2t')
        values_orig = messages.first_resolution_values()
        values = aggregator.do_manipulation(values_orig)
        assert len(values) == 1
        keys_res = list(values.keys())
        assert keys_res[0] == Step(0, 24, 415, 24, 2)

    #include first and last step using half weights for them
    def test_average_halfweights(self):
        ctx = MockedExecutionContext(config_dict, False)
        grib_reader = GRIBReader(ctx.get('input.file'))
        grib_info = grib_reader.get_grib_info({'shortName': '2t'})
        aggregator = Aggregator(aggr_step=24,
                                aggr_type=AVERAGE,
                                aggr_halfweights=True,
                                input_step=grib_info.input_step,
                                step_type=grib_info.type_of_param,
                                start_step=24,
                                mv_grib=grib_info.mv,
                                end_step=24,
                                unit_time=24,
                                force_zero_array=False)
        messages = grib_reader.select_messages(shortName='2t')
        values_orig = messages.first_resolution_values()
        values = aggregator.do_manipulation(values_orig)
        assert len(values) == 1
        keys_res = list(values.keys())
        assert keys_res[0] == Step(0, 24, 415, 24, 2)

    def test_accumulation(self):
        ctx = MockedExecutionContext(config_dict, False)
        grib_reader = GRIBReader(ctx.get('input.file'))
        grib_info = grib_reader.get_grib_info({'shortName': '2t'})
        aggregator = Aggregator(aggr_step=6,
                                aggr_type=ACCUMULATION,
                                aggr_halfweights=False,
                                input_step=grib_info.input_step,
                                step_type=grib_info.type_of_param,
                                start_step=0,
                                mv_grib=grib_info.mv,
                                end_step=24,
                                unit_time=24,
                                force_zero_array=False)
        messages = grib_reader.select_messages(shortName='2t')
        values_orig = messages.first_resolution_values()
        values = aggregator.do_manipulation(values_orig)
        assert len(values) == 4
        keys_res = list(values.keys())
        assert keys_res[0] == Step(0, 6, 415, 6, 2)
        assert keys_res[-1] == Step(18, 24, 415, 6, 2)
