import bisect
import collections
import gc

import numexpr as ne
import numpy as np
from pyg2p.main.domain.step import Step

from pyg2p.main.exceptions import ApplicationException
from pyg2p.util.logger import Logger
from pyg2p.util.numeric import mask_it

# types of manipulation

AVERAGE = 'average'
ACCUMULATION = 'accumulation'
INSTANTANEOUS = 'instantaneous'

# values of key stepType from grib
PARAM_INSTANT = 'instant'
PARAM_AVG = 'avg'
PARAM_CUM = 'accum'


class Aggregator(object):

    def __init__(self, **kwargs):

        self._mv_grib = kwargs.get('mv_grib')
        self._step_type = kwargs.get('step_type')  # stepType from grib
        self._input_step = int(kwargs.get('input_step'))  # timestep from grib. should be in hours

        self._unit_time = int(kwargs.get('unit_time'))
        self._aggregation_step = int(kwargs.get('aggr_step'))
        self._aggregation = kwargs.get('aggr_type')  # type of manipulation
        self._force_zero = kwargs.get('force_zero_array')  # if true, accumulation will consider zero array as GRIB at step 0.

        self._start = int(kwargs.get('start_step'))
        self._end = int(kwargs.get('end_step'))
        self._second_t_res = kwargs.get('sec_temp_res')

        self._logger = Logger.get_logger()

        if self._input_step != 0:
            self._usable_start = (self._start - self._aggregation_step)
            if self._usable_start < 0:
                self._usable_start = 0
        else:
            self._usable_start = self._start

        # dict of functions. Substitutes "if then else" pattern in do_manipulation
        self._functs = {ACCUMULATION: self._cumulation,
                        AVERAGE: self._average,
                        INSTANTANEOUS: self._instantaneous}

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def change_end_step(self,end_first_res):
        self._log('Changing end step to {}'.format(end_first_res))
        self._end = end_first_res

    def get_real_start_end_steps(self):
        return self._usable_start, self._end

    def do_manipulation(self, values):
        log_message = '\nAggregation {} with step {} '\
                      'for {} values from {} to {} '\
                      '[real start: {}]'.format(self._aggregation, self._aggregation_step,
                                                self._step_type, self._start,
                                                self._end, self._usable_start)
        self._log(log_message, 'INFO')
        self._log('******** **** MANIPULATION **** *************')
        res = self._functs[self._aggregation](values)
        gc.collect()
        return res

    def _cumulation(self, values):

        out_values = {}
        resolution = values.keys()[0].resolution
        shape_iter = values[values.keys()[0]].shape
        v_ord = collections.OrderedDict(sorted(dict((k.end_step, v_) for (k, v_) in values.iteritems()).iteritems(), key=lambda k: k))
        self._log('Accumulation at resolution: {}'.format(resolution))

        if self._start == 0:
            self._log('start 0: change to the first timestep {}'.format(self._aggregation_step))
            self._start = self._aggregation_step

        created_zero_array = False
        for iter_ in xrange(self._start, self._end + 1, self._aggregation_step):
            if iter_ not in v_ord.keys():

                ind_next_ts = bisect.bisect_left(v_ord.keys(), iter_)
                next_ts = v_ord.keys()[ind_next_ts]
                # TODO CHECK if mask is necessary here
                # v_nts_ma = mask_it(v_ord[next_ts], self._mv_grib)
                v_nts_ma = v_ord[next_ts]

                ind_originalts = bisect.bisect_right(v_ord.keys(), iter_)
                if ind_originalts == ind_next_ts:
                    ind_originalts -= 1
                originalts = v_ord.keys()[ind_originalts]
                # TODO CHECK if mask is necessary here
                # v_ots_ma = mask_it(v_ord[originalts], self._mv_grib)
                v_ots_ma = v_ord[originalts]

                if self._logger.is_debug:
                    self._log('Message {} not in {}.'.format(iter_, str(v_ord.keys())))
                    self._log('Creating grib[{}] as grib[{}]+(grib[{}]-grib[{}])*(({}-{})/({}-{}))'.format(iter_, originalts, next_ts, originalts, iter_, originalts, next_ts, originalts))

                v_out = ne.evaluate('v_ots_ma + (v_nts_ma-v_ots_ma)*((iter_ - originalts)/(next_ts-originalts))')
                # TODO CHECK if mask is necessary here
                # v_ord[iter_] = mask_it(v_out, self._mv_grib)
                v_ord[iter_] = v_out

            if iter_ - self._aggregation_step >= 0 and iter_ - self._aggregation_step not in v_ord.keys() and not created_zero_array:
                ind_next_ts = bisect.bisect_left(v_ord.keys(), iter_ - self._aggregation_step)
                next_ts = v_ord.keys()[ind_next_ts]

                if iter_ - self._aggregation_step == 0:
                    if self._logger.is_debug:
                        self._log('Message 0 not in dataset. Creating it as zero values array')
                    # TODO CHECK if mask is necessary here
                    # v_ord[0] = mask_it(np.zeros(shape_iter), self._mv_grib, shape_iter)
                    v_ord[0] = np.zeros(shape_iter)
                    originalts = 0
                    created_zero_array = True
                else:
                    # TODO CHECK if mask is necessary here
                    # v_nts_ma = mask_it(v_ord[next_ts], self._mv_grib)
                    v_nts_ma = v_ord[next_ts]
                    ind_originalts = bisect.bisect_right(v_ord.keys(), iter_ - self._aggregation_step)
                    if ind_originalts == ind_next_ts:
                        ind_originalts -= 1
                    originalts = v_ord.keys()[ind_originalts]
                    # variables needed for numexpr evaluator namespace
                    # TODO CHECK if mask is necessary here
                    # v_ots_ma = mask_it(v_ord[originalts], self._mv_grib)
                    v_ots_ma = v_ord[originalts]

                    if self._logger.is_debug:
                        self._log('Creating message grib[{}] as grib[{}]+(grib[{}]-grib[{}])*(({}-{})/({}-{}))'.format(iter_ - self._aggregation_step, originalts, next_ts, originalts, iter_, originalts, next_ts, originalts))

                    v_out = ne.evaluate('v_ots_ma + (v_nts_ma-v_ots_ma)*((iter_ - originalts)/(next_ts-originalts))')
                    # TODO CHECK if mask is necessary here
                    # v_ord[iter_ - self._aggregation_step] = mask_it(v_out, self._mv_grib)
                    v_ord[iter_ - self._aggregation_step] = v_out

            if iter_ - self._aggregation_step == 0 and self._force_zero:
                # forced ZERO array...instead of taking the grib
                # TODO CHECK if mask is necessary here
                # v_iter_1_ma = mask_it(np.zeros(shape_iter), self._mv_grib, shape_iter)
                v_iter_1_ma = np.zeros(shape_iter)
            else:
                # Take the 0 step grib.
                # It could be created before as zero-array,
                # if 0 step is not present in the grib dataset (see line 117)
                # TODO CHECK if mask is necessary here
                # v_iter_1_ma = mask_it(v_ord[iter_ - self._aggregation_step], self._mv_grib)
                v_iter_1_ma = v_ord[iter_ - self._aggregation_step]

            # variables needed for numexpr evaluator namespace. DO NOT DELETE!!!
            # need to create the out array first as zero array, for issue in missing values for certain gribs
            # TODO CHECK if mask is necessary here
            # v_iter_ma = mask_it(np.zeros(shape_iter), self._mv_grib, shape_iter)
            v_iter_ma = np.zeros(shape_iter)
            # TODO CHECK if mask is necessary here and convert to numexpr
            # v_iter_ma += mask_it(v_ord[iter_], self._mv_grib)
            v_iter_ma += v_ord[iter_]

            _unit_time = self._unit_time
            _aggr_step = self._aggregation_step
            key = Step(iter_ - self._aggregation_step, iter_, resolution, self._aggregation_step)
            if self._logger.is_debug:
                self._log('out[{}] = (grib[{}] - grib[{}])  * ({}/{}))'.format(key, iter_, (iter_ - self._aggregation_step), self._unit_time, self._aggregation_step))

            # TODO CHECK if mask is necessary here
            # out_value = mask_it(ne.evaluate("(v_iter_ma-v_iter_1_ma)*_unit_time/_aggr_step"), self._mv_grib)
            out_value = ne.evaluate('(v_iter_ma-v_iter_1_ma)*_unit_time/_aggr_step')
            out_values[key] = out_value

        return out_values

    def _average(self, values):

        if self._step_type in [PARAM_CUM]:
            raise ApplicationException.get_exc(6100, details='Manipulation {} for parameter type: {}'.format(self._aggregation, self._step_type))
        else:

            out_values = {}
            first_key = values.keys()[0]
            resolution_1 = first_key.resolution
            shape_iter = values[first_key].shape

            v_ord = collections.OrderedDict(sorted(dict((k.end_step, v_) for (k, v_) in values.iteritems()).iteritems(), key=lambda k: k))
            if self._start > 0 and not self._second_t_res:
                iter_start = self._start - self._aggregation_step + 1
            elif self._second_t_res:
                iter_start = self._start
            else:
                iter_start = 0

            for iter_ in xrange(iter_start, self._end - self._aggregation_step + 2, self._aggregation_step):

                if self._start == 0:
                    iter_from = iter_ + 1
                    iter_to = iter_ + self._aggregation_step + 1
                else:
                    iter_from = iter_
                    iter_to = iter_ + self._aggregation_step

                # TODO CHECK: maybe we don't need to mask here
                # temp_sum = mask_it(np.zeros(shape_iter), self._mv_grib, shape_iter)
                temp_sum = np.zeros(shape_iter)

                for iterator_avg in xrange(iter_from, iter_to, 1):
                    v_ord_keys = v_ord.keys()
                    if iterator_avg in v_ord_keys:
                        if self._logger.is_debug:
                            self._log('temp_sum += grib[{}]'.format(iterator_avg))
                        # TODO CHECK: maybe we don't need to mask here
                        # v_ma = mask_it(v_ord[iterator_avg], self._mv_grib)
                        v_ma = v_ord[iterator_avg]
                    else:
                        ind_next_ = bisect.bisect_left(v_ord_keys, iterator_avg)
                        next_ = v_ord_keys[ind_next_]
                        if self._logger.is_debug:
                            self._log('temp_sum += grib[{}] from -> grib[{}]'.format(iterator_avg, next_))
                        # TODO CHECK: maybe we don't need to mask here
                        # v_ma = mask_it(v_ord[next_], self._mv_grib)
                        v_ma = v_ord[next_]
                    ne.evaluate('temp_sum + v_ma', out=temp_sum)

                key = Step(iter_, iter_ + self._aggregation_step, resolution_1, self._aggregation_step)
                if self._logger.is_debug:
                    self._log('out[{}] = temp_sum/{}'.format(key, self._aggregation_step))
                _aggregation_step = self._aggregation_step  # used with numexpress. DO NOT DELETE!
                # TODO CHECK: maybe we don't need to mask here
                # out_values[key] = mask_it(ne.evaluate("temp_sum/_aggregation_step"), self._mv_grib)
                out_values[key] = ne.evaluate('temp_sum/_aggregation_step')

            return out_values

    def _find_start(self):
        start = self._start - self._aggregation_step if self._start - self._aggregation_step > 0 else self._start
        if self._step_type == PARAM_AVG:
            start = self._start + self._input_step
        return start

    def _instantaneous(self, values):
        if self._step_type in [PARAM_CUM]:
            raise ApplicationException.get_exc(6100, details='Manipulation {} for parameter type: {}'.format(self._aggregation, self._step_type))
        else:
            out_values = {}
            start = self._find_start()
            resolution_1 = values.keys()[0].resolution
            shape_iter = values[values.keys()[0]].shape

            # sets a new dict with different key (using only endstep)
            v_ord = collections.OrderedDict(sorted(dict((k.end_step, v_) for (k, v_) in values.iteritems()).iteritems(), key=lambda k: k))

            for iter_ in range(start, self._end + 1, self._aggregation_step):
                # TODO CHECK: maybe we don't need to mask here
                # res_inst = mask_it(np.zeros(shape_iter), self._mv_grib, shape_iter)
                res_inst = np.zeros(shape_iter)
                key = Step(iter_, iter_, resolution_1, self._aggregation_step)
                if iter_ in v_ord.keys():
                    if self._logger.is_debug:
                        self._log('out[{}] = grib[{}]'.format(key, iter_))
                    # TODO CHECK: maybe we don't need to mask here and use numexpr
                    # res_inst += mask_it(v_ord[iter_], self._mv_grib)
                    res_inst += v_ord[iter_]
                else:
                    if iter_ == 0:
                        # left out as zero arrays if 0 step is not in the grib
                        if self._logger.is_debug:
                            self._log('out[{}] = zeros'.format(key))
                        pass
                    else:
                        ind_next_ = bisect.bisect_right(v_ord.keys(), iter_)
                        next_ = v_ord.keys()[ind_next_]
                        if self._logger.is_debug:
                            self._log('out[{}] = grib[{}]'.format((key, next_)))
                        # TODO CHECK: maybe we don't need to mask here and use numexpr
                        # res_inst += mask_it(v_ord[next_], self._mv_grib)
                        res_inst += v_ord[next_]
                out_values[key] = res_inst

            return out_values
