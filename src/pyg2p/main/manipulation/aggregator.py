import bisect
import collections
import logging
import gc

import numexpr as ne
import numpy as np
from numpy import ma

from ...util import numeric
from ... import Loggable, Step
from ...exceptions import ApplicationException, NOT_IMPLEMENTED

# types of manipulation
AVERAGE = 'average'
ACCUMULATION = 'accumulation'
INSTANTANEOUS = 'instantaneous'

# values of key stepType from grib
PARAM_INSTANT = 'instant'
PARAM_AVG = 'avg'
PARAM_CUM = 'accum'


class Aggregator(Loggable):

    def __init__(self, **kwargs):
        super().__init__()
        self._mv_grib = kwargs.get('mv_grib')
        self._step_type = kwargs.get('step_type')  # stepType from grib
        self._input_step = int(kwargs.get('input_step'))  # timestep from grib. should be in hours

        self._unit_time = int(kwargs.get('unit_time'))
        self._aggregation_step = int(kwargs.get('aggr_step'))
        self._aggregation = kwargs.get('aggr_type')  # type of manipulation
        self._aggregation_halfweights = kwargs.get('aggr_halfweights')  # include first and last step using half weights for them
        self._force_zero = kwargs.get('force_zero_array')  # if true, accumulation will use a zero array at step 0.

        self._start = int(kwargs.get('start_step'))
        self._end = int(kwargs.get('end_step'))
        self._second_t_res = kwargs.get('sec_temp_res')

        if self._input_step != 0:
            self._usable_start = (self._start - self._aggregation_step)
            if self._usable_start < 0:
                self._usable_start = 0
        else:
            self._usable_start = self._start

        # dict of functions. Substitutes "if then else" pattern in do_manipulation
        self._functs = {ACCUMULATION: self._accumulation,
                        AVERAGE: self._average,
                        INSTANTANEOUS: self._instantaneous}

    def change_end_step(self,end_first_res):
        self._log('Changing end step to {}'.format(end_first_res))
        self._end = end_first_res

    def get_real_start_end_steps(self):
        return self._usable_start, self._end

    def do_manipulation(self, values):
        log_message = f'\nAggregation {self._aggregation} with step {self._aggregation_step} '\
                      f'for {self._step_type} values from {self._start} to {self._end} '\
                      f'[real start: {self._usable_start}]'
        self._log(log_message, 'INFO')
        self._log('******** **** MANIPULATION **** *************')
        res = self._functs[self._aggregation](values)
        gc.collect()
        return res

    def _accumulation(self, values):

        out_values = {}
        item_keys = list(values.keys())[0]
        resolution = item_keys.resolution
        level = item_keys.level
        shape_iter = values[item_keys].shape
        v_ord = collections.OrderedDict(sorted(dict((k.end_step, v_) for (k, v_) in values.items()).items(), key=lambda k: k))
        self._log('Accumulation at resolution: {}'.format(resolution))

        if self._start == 0:
            self._log('start 0: change to the first timestep {}'.format(self._aggregation_step))
            self._start = self._aggregation_step

        created_zero_array = False
        for iter_ in range(self._start, self._end + 1, self._aggregation_step):
            v_ord_keys = list(v_ord.keys())
            if iter_ not in v_ord_keys:

                ind_next_ts = bisect.bisect_left(v_ord_keys, iter_)
                next_ts = v_ord_keys[ind_next_ts]
                v_nts_ma = v_ord[next_ts]

                ind_originalts = bisect.bisect_right(v_ord_keys, iter_)
                if ind_originalts == ind_next_ts:
                    ind_originalts -= 1
                originalts = v_ord_keys[ind_originalts]
                v_ots_ma = v_ord[originalts]

                if self._logger.isEnabledFor(logging.DEBUG):
                    self._log(f'Message {iter_} not in {v_ord_keys}.')
                    self._log(f'Creating grib[{iter_}] as grib[{originalts}]+(grib[{next_ts}]-grib[{originalts}])*(({iter_}-{originalts})/({next_ts}-{originalts}))')

                v_out = ne.evaluate('v_ots_ma + (v_nts_ma-v_ots_ma)*((iter_ - originalts)/(next_ts-originalts))')
                v_ord[iter_] = ma.masked_where(numeric.get_masks(v_ots_ma, v_nts_ma), v_out, copy=False)

            if iter_ - self._aggregation_step >= 0 and iter_ - self._aggregation_step not in v_ord_keys and not created_zero_array:
                ind_next_ts = bisect.bisect_left(v_ord_keys, iter_ - self._aggregation_step)
                next_ts = v_ord_keys[ind_next_ts]

                if iter_ - self._aggregation_step == 0:
                    self._log('Message 0 not in dataset. Creating it as zero values array')
                    v_ord[0] = np.zeros(shape_iter)
                    originalts = 0  # do not delete: used by numexpr evaluation
                    created_zero_array = True
                else:
                    v_nts_ma = v_ord[next_ts]
                    ind_originalts = bisect.bisect_right(v_ord_keys, iter_ - self._aggregation_step)
                    if ind_originalts == ind_next_ts:
                        ind_originalts -= 1
                    originalts = v_ord_keys[ind_originalts]
                    # variables needed for numexpr evaluator namespace
                    v_ots_ma = v_ord[originalts]

                    if self._logger.isEnabledFor(logging.DEBUG):
                        self._log(f'Creating message grib[{iter_ - self._aggregation_step}]=grib[{originalts}]+(grib[{next_ts}]-grib[{originalts}])*(({iter_}-{originalts})/({next_ts}-{originalts}))')
                    v_out = ne.evaluate('v_ots_ma + (v_nts_ma-v_ots_ma)*((iter_ - originalts)/(next_ts-originalts))')
                    v_ord[iter_ - self._aggregation_step] = ma.masked_where(numeric.get_masks(v_ots_ma, v_nts_ma), v_out, copy=False)

            if iter_ - self._aggregation_step == 0 and self._force_zero:
                # forced ZERO array...instead of taking the grib
                v_iter_1_ma = np.zeros(shape_iter)
            else:
                # Take the 0 step grib.
                # It could be created before as zero-array,
                # if 0 step is not present in the grib dataset (see line 117)
                v_iter_1_ma = v_ord[iter_ - self._aggregation_step]

            # variables needed for numexpr evaluator namespace. DO NOT DELETE!!!
            # need to create the out array first as zero array, for issue in missing values for certain gribs
            v_iter_ma = np.zeros(shape_iter)
            v_iter_ma += v_ord[iter_]
            _unit_time = self._unit_time
            _aggr_step = self._aggregation_step
            key = Step(iter_ - self._aggregation_step, iter_, resolution, self._aggregation_step, level)
            out_value = ne.evaluate('(v_iter_ma-v_iter_1_ma)*_unit_time/_aggr_step')
            out_values[key] = ma.masked_where(numeric.get_masks(v_iter_ma, v_iter_1_ma), out_value, copy=False)

            if self._logger.isEnabledFor(logging.DEBUG):
                self._log(f'out[{key}] = (grib[{iter_}] - grib[{(iter_ - self._aggregation_step)}])  * ({self._unit_time}/{self._aggregation_step}))')

        return out_values

    def _average(self, values):

        if self._step_type in [PARAM_CUM]:
            raise ApplicationException.get_exc(NOT_IMPLEMENTED, details=f'Manipulation {self._aggregation} for parameter type: {self._step_type}')
        else:

            out_values = {}
            first_key = list(values.keys())[0]
            resolution_1 = first_key.resolution
            level = first_key.level
            shape_iter = values[first_key].shape

            v_ord = collections.OrderedDict(sorted(dict((k.end_step, v_) for (k, v_) in values.items()).items(), key=lambda k: k))
            if self._start == 0 or self._second_t_res:
                iter_start = self._start
                iter_end = self._end - self._aggregation_step + 2
            else:
                iter_start = self._start - self._aggregation_step
                iter_end = self._end - self._aggregation_step + 1

            for iter_ in range(iter_start, iter_end, self._aggregation_step):
                if self._aggregation_halfweights or self._start == 0:
                    iter_from = iter_ 
                    iter_to = iter_ + self._aggregation_step + 1
                else:
                    iter_from = iter_ + 1
                    iter_to = iter_ + self._aggregation_step + 1
                temp_sum = np.zeros(shape_iter)
                v_ord_keys = list(v_ord.keys())

                if self._aggregation_halfweights:
                    count_steps=-1
                    for iterator_avg in range(iter_from, iter_to, 1):
                        if iterator_avg in v_ord_keys:                
                            count_steps=count_steps+1
                    if count_steps>0:
                        dt1=np.round(self._aggregation_step/count_steps,0)
                        dt2=np.round(dt1/2,0)

                        for iterator_avg in range(iter_from, iter_to, 1):
                            if iterator_avg in v_ord_keys:
                                if self._logger.isEnabledFor(logging.DEBUG):
                                    self._log(f'temp_sum += grib[{iterator_avg}]')
                                if iterator_avg==iter_from or iterator_avg==(iter_to-1):
                                    v_ma = v_ord[iterator_avg]*dt2
                                    print("Iterator: {} weight: {}".format(iterator_avg,dt2))
                                else:
                                    v_ma = v_ord[iterator_avg]*dt1
                                    print("Iterator: {} weight: {}".format(iterator_avg,dt1))
                                ne.evaluate('temp_sum + v_ma', out=temp_sum)
                else:
                    for iterator_avg in range(iter_from, iter_to, 1):
                        if iterator_avg in v_ord_keys:
                            if self._logger.isEnabledFor(logging.DEBUG):
                                self._log(f'temp_sum += grib[{iterator_avg}]')
                            v_ma = v_ord[iterator_avg]
                        else:
                            ind_next_ = bisect.bisect_left(list(v_ord_keys), iterator_avg)
                            next_ = list(v_ord_keys)[ind_next_]
                            if self._logger.isEnabledFor(logging.DEBUG):
                                self._log(f'temp_sum += grib[{iterator_avg}] from -> grib[{next_}]')
                            v_ma = v_ord[next_]
                        ne.evaluate('temp_sum + v_ma', out=temp_sum)

                # mask result with all maskes from GRIB original values used in average (if existing any)
                # temp_sum = ma.masked_where(pyg2p.util.numeric.get_masks(v_ord.values()), temp_sum, copy=False)
                key = Step(iter_, iter_ + self._aggregation_step, resolution_1, self._aggregation_step, level)
                # used with numexpress that doesn't access self. DO NOT DELETE!
                aggregation_step = self._aggregation_step
                res = ne.evaluate('temp_sum/aggregation_step')
                # mask result with all maskes from GRIB original values used in average (if existing any)
                out_values[key] = ma.masked_where(numeric.get_masks(v_ord.values()), res, copy=False)
                if self._logger.isEnabledFor(logging.DEBUG):
                    self._log(f'out[{key}] = temp_sum/{self._aggregation_step}')

            return out_values

    def _find_start(self):
        start = self._start - self._aggregation_step if self._start - self._aggregation_step > 0 else self._start
        if self._step_type == PARAM_AVG:
            start = self._start + self._input_step
        return start

    def _instantaneous(self, values):
        if self._step_type in [PARAM_CUM]:
            raise ApplicationException.get_exc(NOT_IMPLEMENTED, details=f'Manipulation {self._aggregation} for parameter type: {self._step_type}')
        else:
            out_values = {}
            start = self._find_start()

            # sets a new dict with different key (using only endstep)
            v_ord = collections.OrderedDict(sorted(dict((k.end_step, v_) for (k, v_) in values.items()).items(), key=lambda k: k))
            v_ord_keys = list(v_ord.keys())
            values_keys = list(values.keys())
            resolution_1 = values_keys[0].resolution
            level = values_keys[0].level
            shape_iter = values[values_keys[0]].shape
            for iter_ in range(start, self._end + 1, self._aggregation_step):
                res_inst = np.zeros(shape_iter)
                key = Step(iter_, iter_, resolution_1, self._aggregation_step, level)
                if iter_ in v_ord_keys:
                    if self._logger.isEnabledFor(logging.DEBUG):
                        self._log(f'out[{key}] = grib[{iter_}]')
                    res_inst += v_ord[iter_]
                else:
                    if iter_ == 0:
                        # left out as zero arrays if 0 step is not in the grib
                        if self._logger.isEnabledFor(logging.DEBUG):
                            self._log(f'out[{key}] = zeros')
                        pass
                    else:
                        ind_next_ = bisect.bisect_right(v_ord_keys, iter_)
                        next_ = list(v_ord_keys)[ind_next_]
                        if self._logger.isEnabledFor(logging.DEBUG):
                            self._log(f'out[{key}] = grib[{next_}]')
                        res_inst += v_ord[next_]
                out_values[key] = res_inst

            return out_values
