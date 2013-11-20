import collections
import bisect
import numpy as np

#from gribpcraster.application.domain.Messages import Values
from gribpcraster.exc.ApplicationException import ApplicationException
from util.logger.Logger import Logger
import gribpcraster.application.ExecutionContext as ex
from util.numeric.numeric import _mask_it
from gribpcraster.application.domain.Key import Key
#types of manipulation

MANIPULATION_AVG = 'average'
MANIPULATION_ACCUM = 'accumulation'
MANIPULATION_INSTANT = 'instantaneous'

#values of key stepType from grib
PARAM_INSTANT = 'instant'
PARAM_AVG = 'avg'
PARAM_CUM = 'accum'

class Manipulator(object):
    def __init__(self, aggr_step, aggr_type, input_step, step_type_, start_step, end_step, unit_time, mv_, sec_temp_res=False, lastFirstResMessage=None):

        self._mvGrib = mv_
        self._unit_time=int(unit_time)
        self._aggregation_step = int(aggr_step)
        self._aggregation = aggr_type  # type of manipulation
        self._step_type = step_type_  # stepType from grib
        self._input_step = int(input_step)  # timestep from grib. should be in hours
        self._start=int(start_step)
        self._end=int(end_step)
        self._second_t_res = sec_temp_res
        self._lastFirstResMess = lastFirstResMessage
        import gribpcraster.application.ExecutionContext as ex
        self._logger = Logger('Manipulator', loggingLevel=ex.global_logger_level)

        if self._input_step != 0:
            self._usable_start = (self._start -self._aggregation_step)
            if self._usable_start < 0:
                self._usable_start = 0
        else:
            self._usable_start = self._start
        self._log('Aggregation %s with step %s for %s values from %d to %d [considering from ts=%d]'
                  %(self._aggregation,self._aggregation_step,self._step_type, self._start, self._end, self._usable_start))

        #dict of functions. Substitutes "if then else" pattern in doManipulation
        self._functs = {MANIPULATION_ACCUM: self._cumulation, MANIPULATION_AVG: self._average, MANIPULATION_INSTANT: self._instantaneous}

    #input is dict of values[start-end-res]
    #out is values(end)
    def _convert_key_to_endstep(self, values):
        v_by_endstep={}
        #sets a new dict with different key (using only endstep)
        for k,v in values.iteritems():
            v_by_endstep[int(k.end_step)]= v
        return v_by_endstep

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def change_end_step(self,end_first_res):
        self._log('Changing end step to %d'%end_first_res)
        self._end = end_first_res

    def doManipulation(self, values):
        self._log('******** **** MANIPULATION **** *************')
        return self._functs[self._aggregation](values)

    def _cumulation(self, values):

        if self._step_type in [PARAM_INSTANT, PARAM_CUM, PARAM_AVG]:
            out_values = {}
            res = values.keys()[0].resolution
            v = self._convert_key_to_endstep(values)  # original key is 'start-end-resolution'
            v_ord = collections.OrderedDict(sorted(v.items(), key=lambda k: k[0]))
            self._log('Cumulation at resolution: %s' % res)

            if self._start == 0:
                self._log('start 0: change to the first aggregation_timestep %d' % self._aggregation_step)
                self._start = self._aggregation_step

            created_zero_array = False
            for iter_ in range(self._start, self._end+1, self._aggregation_step):
                #raw_input('iter --> %d,start: %d, end:%d, step: %d' % (iter_,self._start, int(self._end)+1, self._aggregation_step))
                if iter_ not in v_ord.keys():
                    ind_next_ts= bisect.bisect_left(v_ord.keys(), iter_)
                    next_ts = v_ord.keys()[ind_next_ts]

                    v_nts_ma = _mask_it(v[next_ts], self._mvGrib)
                    self._log('Message %d not in dataset. Creating it. Masking with %.2f'%(iter_, self._mvGrib))

                    ind_originalts= bisect.bisect_right(v_ord.keys(), iter_)
                    if ind_originalts == ind_next_ts:
                        ind_originalts -= 1
                    originalts=v_ord.keys()[ind_originalts]
                    v_ots_ma = _mask_it(v[originalts], self._mvGrib)

                    self._log('Trying to create message grib:%d as grib:%d+(grib:%d-grib:%d)*((%d-%d)/(%d-%d))'
                                  %(iter_,originalts,next_ts,originalts,iter_,originalts,next_ts,originalts))
                    v_out = v_ots_ma + (v_nts_ma-v_ots_ma)*((iter_ - originalts)/(next_ts-originalts))
                    v[iter_] = _mask_it(v_out, self._mvGrib)

                if iter_ - self._aggregation_step >= 0 and iter_ - self._aggregation_step not in v_ord.keys() and not created_zero_array:
                    ind_next_ts= bisect.bisect_left(v_ord.keys(), iter_-self._aggregation_step)
                    next_ts=v_ord.keys()[ind_next_ts]
                    v_nts_ma = _mask_it(v[next_ts], self._mvGrib)

                    if iter_ - self._aggregation_step == 0:
                        self._log('Message %d not in dataset. Creating it as zero values array'%(iter_- self._aggregation_step))
                        v[iter_-self._aggregation_step] = _mask_it(np.zeros(v[next_ts].shape), self._mvGrib)
                        originalts = 0
                        created_zero_array = True
                    else:
                        self._log('Message %d not in dataset. Creating it. Masking with %.2f'%(iter_-self._aggregation_step , self._mvGrib))

                        ind_originalts= bisect.bisect_right(v_ord.keys(), iter_-self._aggregation_step)
                        if ind_originalts == ind_next_ts:
                            ind_originalts-=1
                        originalts=v_ord.keys()[ind_originalts]
                        v_ots_ma = _mask_it(v[originalts], self._mvGrib)

                        self._log('Trying to create message grib:%d as grib:%d+(grib:%d-grib:%d)*((%d-%d)/(%d-%d))'
                                  %(iter_-self._aggregation_step,originalts,next_ts,originalts,iter_,originalts,next_ts,originalts))
                        v_out = v_ots_ma + (v_nts_ma-v_ots_ma)*((iter_ - originalts)/(next_ts-originalts))
                        v[iter_-self._aggregation_step] = _mask_it(v_out, self._mvGrib)

                key = Key(iter_-self._aggregation_step, iter_, res, self._aggregation_step)
                self._log('out[%s] = (grib:%d - grib:%d)  * (%d/%d))'%(key, iter_, (iter_ - self._aggregation_step), self._unit_time, self._aggregation_step))
                v_iter_ma = _mask_it(v[iter_], self._mvGrib)

                #if iter_- self._aggregation_step == 0:
                #    # forced ZERO array...
                #    #raw_input('Creating zeros...')
                #    v_iter_1_ma = _mask_it(np.zeros(v[0].shape), self._mvGrib)
                #else:
                #    v_iter_1_ma = _mask_it(v[iter_- self._aggregation_step], self._mvGrib)

                v_iter_1_ma = _mask_it(v[iter_- self._aggregation_step], self._mvGrib)
                out_value = _mask_it((v_iter_ma-v_iter_1_ma)*(self._unit_time/self._aggregation_step), self._mvGrib)
                out_values[key] = out_value

        ordered = collections.OrderedDict(sorted(out_values.items(), key=lambda (k,v): (int(k.end_step),v)))
        return ordered

    def _average(self, values):

        if self._step_type in [PARAM_CUM]:
            raise ApplicationException.get_programmatic_exc(6100, details="Manipulation %d for parameter type: %s"%(self._aggregation, self._step_type))
        elif self._step_type in [PARAM_INSTANT, PARAM_AVG]:

            out_values = {}

            resolution_1 = values.keys()[0].resolution
            shape_iter = values[values.keys()[0]].shape

            v = self._convert_key_to_endstep(values)
            v_ord=collections.OrderedDict(sorted(v.items(), key=lambda k: k[0]))
            if self._start > 0 and not self._second_t_res:
                iter_start = self._start-self._aggregation_step+1
            elif self._second_t_res:
                iter_start = self._start
            else:
                iter_start = 0

            for iter_ in range(iter_start, self._end-self._aggregation_step + 2, self._aggregation_step):

                if self._start == 0:
                    iter_from=iter_+1
                    iter_to=iter_+self._aggregation_step+1
                else:
                    iter_from=iter_
                    iter_to=iter_+self._aggregation_step

                temp_sum =_mask_it(np.zeros(shape_iter), self._mvGrib, shape_iter)

                for iterator_avg  in range(iter_from, iter_to, 1):
                    #if (iterator_avg % self._input_step)==0:
                     if iterator_avg in v_ord.keys():
                        self._log('temp_sum += grib[%d]'%iterator_avg, 'DEBUG')
                        v_ma = _mask_it(v[iterator_avg], self._mvGrib)
                        temp_sum += v_ma
                     else:
                        ind_next_=bisect.bisect_left(v_ord.keys(), iterator_avg)
                        next_=v_ord.keys()[ind_next_]
                        self._log('temp_sum += grib[%d] from -> grib[%d]'%(iterator_avg, next_))
                        v_ma = _mask_it(v[next_], self._mvGrib)
                        temp_sum += v_ma
                result_iter_avg = _mask_it(temp_sum/self._aggregation_step,self._mvGrib)
                key = Key(iter_, iter_+self._aggregation_step, resolution_1, self._aggregation_step)
                self._log('out[%s] = temp_sum / %d' % (key, self._aggregation_step))
                out_values[key] = result_iter_avg
        ordered = collections.OrderedDict(sorted(out_values.items(), key = lambda (k,v) : (int(k.end_step), v)))
        return ordered

    def _instantaneous(self, values):
        if self._step_type in [PARAM_CUM]:
            raise ApplicationException.get_programmatic_exc(6100, details="Manipulation %d for parameter type: %s"%(self._aggregation, self._step_type))
        elif self._step_type in [PARAM_INSTANT, PARAM_AVG]:
            out_values = {}
            start = self._start
            if self._step_type==PARAM_AVG:
                start=self._start+self._input_step
            resolution_1 = values.keys()[0].resolution
            shape_iter = values[values.keys()[0]].shape
            #sets a new dict with different key (using only endstep)
            v = self._convert_key_to_endstep(values)
            v_ord=collections.OrderedDict(sorted(v.items(), key = lambda k : k[0]))

            for iter_ in range(start, self._end + 1, self._aggregation_step):
                key = Key(iter_, iter_, resolution_1, self._aggregation_step)
                if iter_ in v_ord.keys():
                    self._log('out[%s] = grib:%d'%(key,iter_))
                    res_inst = _mask_it(v[iter_], self._mvGrib)
                else:
                    ind_next_=bisect.bisect_right(v_ord.keys(), iter_)
                    next_=v_ord.keys()[ind_next_]
                    self._log('out[%s] = grib:%d'%(key, next_))
                    res_inst= _mask_it(v[next_], self._mvGrib)
                out_values[key] = res_inst

        ordered = collections.OrderedDict(sorted(out_values.items(), key = lambda (k,v) : (int(k.end_step), v)))
        return ordered

    def getRealStartEndStep(self):
        return self._usable_start, self._end