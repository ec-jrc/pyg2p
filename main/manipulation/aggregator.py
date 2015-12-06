import bisect
import collections
import gc

import numexpr as ne
import numpy as np

from main.domain.Key import Key
from main.exceptions import ApplicationException
from util.logger import Logger
from util.numeric import mask_it

# types of manipulation

MANIPULATION_AVG = 'average'
MANIPULATION_ACCUM = 'accumulation'
MANIPULATION_INSTANT = 'instantaneous'

# values of key stepType from grib
PARAM_INSTANT = 'instant'
PARAM_AVG = 'avg'
PARAM_CUM = 'accum'


class Aggregator(object):

    def __init__(self, aggr_step, aggr_type, input_step, step_type_, start_step, end_step, unit_time, mv_, force_zero_array=False, sec_temp_res=False, lastFirstResMessage=None):

        self._mvGrib = mv_
        self._unit_time = int(unit_time)
        self._aggregation_step = int(aggr_step)
        self._aggregation = aggr_type  # type of manipulation
        self._force_zero = force_zero_array  # if true, accumulation will consider zero array as GRIB at step 0.
        self._step_type = step_type_  # stepType from grib
        self._input_step = int(input_step)  # timestep from grib. should be in hours
        self._start = int(start_step)
        self._end = int(end_step)
        self._second_t_res = sec_temp_res
        self._lastFirstResMess = lastFirstResMessage
        self._logger = Logger.get_logger()

        if self._input_step != 0:
            self._usable_start = (self._start - self._aggregation_step)
            if self._usable_start < 0:
                self._usable_start = 0
        else:
            self._usable_start = self._start
        self._log('Aggregation %s with step %s for %s values from %d to %d [considering from ts=%d]'
                  %(self._aggregation, self._aggregation_step, self._step_type, self._start, self._end, self._usable_start))

        # dict of functions. Substitutes "if then else" pattern in doManipulation
        self._functs = {MANIPULATION_ACCUM: self._cumulation,
                        MANIPULATION_AVG: self._average,
                        MANIPULATION_INSTANT: self._instantaneous}

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def change_end_step(self,end_first_res):
        self._log('Changing end step to %d' % end_first_res)
        self._end = end_first_res

    def do_manipulation(self, values):
        self._log('******** **** MANIPULATION **** *************')
        res = self._functs[self._aggregation](values)
        gc.collect()
        return res

    def _cumulation(self, values):

        out_values = {}
        resolution = values.keys()[0].resolution
        shape_iter = values[values.keys()[0]].shape
        v_ord = collections.OrderedDict(sorted(dict((k.end_step, v_) for (k, v_) in values.iteritems()).iteritems(), key=lambda k: k))
        self._log('Accumulation at resolution: %s' % resolution)

        if self._start == 0:
            self._log('start 0: change to the first aggregation_timestep %d' % self._aggregation_step)
            self._start = self._aggregation_step

        created_zero_array = False
        for iter_ in xrange(self._start, self._end + 1, self._aggregation_step):
            if iter_ not in v_ord.keys():
                self._log('Message %d not in %s. ' % (iter_, str(v_ord.keys())))
                ind_next_ts = bisect.bisect_left(v_ord.keys(), iter_)
                self._log('Found index %d as bisect_left. ' % (ind_next_ts))
                next_ts = v_ord.keys()[ind_next_ts]
                v_nts_ma = mask_it(v_ord[next_ts], self._mvGrib)
                self._log('Message %d not in dataset. Creating it. Masking with %.2f' % (iter_, self._mvGrib))

                ind_originalts = bisect.bisect_right(v_ord.keys(), iter_)
                if ind_originalts == ind_next_ts:
                    ind_originalts -= 1
                originalts = v_ord.keys()[ind_originalts]
                v_ots_ma = mask_it(v_ord[originalts], self._mvGrib)

                self._log('Trying to create message grib:%d as grib:%d+(grib:%d-grib:%d)*((%d-%d)/(%d-%d))'
                              % (iter_, originalts, next_ts, originalts, iter_, originalts, next_ts,originalts))
                v_out = ne.evaluate("v_ots_ma + (v_nts_ma-v_ots_ma)*((iter_ - originalts)/(next_ts-originalts))")
                v_ord[iter_] = mask_it(v_out, self._mvGrib)

            if iter_ - self._aggregation_step >= 0 and iter_ - self._aggregation_step not in v_ord.keys() and not created_zero_array:
                ind_next_ts = bisect.bisect_left(v_ord.keys(), iter_ - self._aggregation_step)
                next_ts = v_ord.keys()[ind_next_ts]


                if iter_ - self._aggregation_step == 0:
                    self._log('Message 0 not in dataset. Creating it as zero values array')
                    v_ord[0] = mask_it(np.zeros(shape_iter), self._mvGrib, shape_iter)
                    originalts = 0
                    created_zero_array = True
                else:
                    self._log('Message %d not in dataset. Creating it. Masking with %.2f' % (iter_ - self._aggregation_step, self._mvGrib))
                    v_nts_ma = mask_it(v_ord[next_ts], self._mvGrib)
                    ind_originalts = bisect.bisect_right(v_ord.keys(), iter_ - self._aggregation_step)
                    if ind_originalts == ind_next_ts:
                        ind_originalts -= 1
                    originalts = v_ord.keys()[ind_originalts]
                    #variables needed for numexpr evaluator namespace
                    v_ots_ma = mask_it(v_ord[originalts], self._mvGrib)

                    self._log('Trying to create message grib:%d as grib:%d+(grib:%d-grib:%d)*((%d-%d)/(%d-%d))'
                              % (iter_ - self._aggregation_step, originalts, next_ts, originalts, iter_, originalts, next_ts, originalts))
                    v_out = ne.evaluate("v_ots_ma + (v_nts_ma-v_ots_ma)*((iter_ - originalts)/(next_ts-originalts))")
                    v_ord[iter_ - self._aggregation_step] = mask_it(v_out, self._mvGrib)

            if iter_ - self._aggregation_step == 0 and self._force_zero:
                # forced ZERO array...instead of taking the grib
                v_iter_1_ma = mask_it(np.zeros(shape_iter), self._mvGrib, shape_iter)
            else:
                # Take the 0 step grib.
                # It could be created before as zero-array,
                # if 0 step is not present in the grib dataset (see line 117)
                v_iter_1_ma = mask_it(v_ord[iter_ - self._aggregation_step], self._mvGrib)

            # variables needed for numexpr evaluator namespace
            # need to create the out array first as zero array, for issue in missing values for certain gribs
            v_iter_ma = mask_it(np.zeros(shape_iter), self._mvGrib, shape_iter)
            v_iter_ma += mask_it(v_ord[iter_], self._mvGrib)

            _unit_time = self._unit_time
            _aggr_step = self._aggregation_step
            key = Key(iter_ - self._aggregation_step, iter_, resolution, self._aggregation_step)
            self._log('out[%s] = (grib:%d - grib:%d)  * (%d/%d))' % (key, iter_, (iter_ - self._aggregation_step), self._unit_time, self._aggregation_step))
            out_value = mask_it(ne.evaluate("(v_iter_ma-v_iter_1_ma)*_unit_time/_aggr_step"), self._mvGrib)
            out_values[key] = out_value

        return out_values

    def _average(self, values):

        if self._step_type in [PARAM_CUM]:
            raise ApplicationException.get_programmatic_exc(6100, details="Manipulation %d for parameter type: %s"%(self._aggregation, self._step_type))
        elif self._step_type in [PARAM_INSTANT, PARAM_AVG]:

            out_values = {}

            resolution_1 = values.keys()[0].resolution
            shape_iter = values[values.keys()[0]].shape

            v_ord = collections.OrderedDict(sorted(dict((k.end_step, v_) for (k, v_) in values.iteritems()).iteritems(), key=lambda k: k))
            if self._start > 0 and not self._second_t_res:
                iter_start = self._start - self._aggregation_step + 1
            elif self._second_t_res:
                iter_start = self._start
            else:
                iter_start = 0

            for iter_ in range(iter_start, self._end - self._aggregation_step + 2, self._aggregation_step):

                if self._start == 0:
                    iter_from = iter_ + 1
                    iter_to = iter_ + self._aggregation_step + 1
                else:
                    iter_from = iter_
                    iter_to = iter_ + self._aggregation_step

                temp_sum = mask_it(np.zeros(shape_iter), self._mvGrib, shape_iter)

                for iterator_avg in range(iter_from, iter_to, 1):

                    if iterator_avg in v_ord.keys():
                        self._log('temp_sum += grib[%d]'%iterator_avg, 'DEBUG')
                        v_ma = mask_it(v_ord[iterator_avg], self._mvGrib)
                        temp_sum += v_ma
                    else:
                        ind_next_ = bisect.bisect_left(v_ord.keys(), iterator_avg)
                        next_ = v_ord.keys()[ind_next_]
                        self._log('temp_sum += grib[%d] from -> grib[%d]' % (iterator_avg, next_))
                        v_ma = mask_it(v_ord[next_], self._mvGrib)
                        temp_sum += v_ma

                _aggregation_step = self._aggregation_step
                key = Key(iter_, iter_ + self._aggregation_step, resolution_1, self._aggregation_step)
                self._log('out[%s] = temp_sum / %d' % (key, self._aggregation_step))

                result_iter_avg = mask_it(ne.evaluate("temp_sum/_aggregation_step"), self._mvGrib)
                out_values[key] = result_iter_avg

        return out_values

    def _find_start(self):
        start = self._start - self._aggregation_step if self._start - self._aggregation_step > 0 else self._start
        if self._step_type == PARAM_AVG:
            start = self._start + self._input_step
        return start

    def _instantaneous(self, values):
        if self._step_type in [PARAM_CUM]:
            raise ApplicationException.get_programmatic_exc(6100, details="Manipulation %d for parameter type: %s"%(self._aggregation, self._step_type))
        elif self._step_type in [PARAM_INSTANT, PARAM_AVG]:
            out_values = {}
            start = self._find_start()
            resolution_1 = values.keys()[0].resolution
            shape_iter = values[values.keys()[0]].shape

            # sets a new dict with different key (using only endstep)
            v_ord = collections.OrderedDict(sorted(dict((k.end_step, v_) for (k, v_) in values.iteritems()).iteritems(), key=lambda k: k))

            for iter_ in range(start, self._end + 1, self._aggregation_step):
                res_inst = mask_it(np.zeros(shape_iter), self._mvGrib, shape_iter)
                key = Key(iter_, iter_, resolution_1, self._aggregation_step)
                if iter_ in v_ord.keys():
                    self._log('out[%s] = grib:%d' % (key, iter_))
                    res_inst += mask_it(v_ord[iter_], self._mvGrib)
                else:
                    if iter_ == 0:
                        # left out as zero arrays if 0 step is not in the grib
                        self._log('out[%s] = zeros' % key)
                        pass
                    else:
                        ind_next_ = bisect.bisect_right(v_ord.keys(), iter_)
                        next_ = v_ord.keys()[ind_next_]
                        self._log('out[%s] = grib:%d' % (key, next_))
                        res_inst += mask_it(v_ord[next_], self._mvGrib)
                out_values[key] = res_inst

        return out_values

    def get_real_start_end_steps(self):
        return self._usable_start, self._end