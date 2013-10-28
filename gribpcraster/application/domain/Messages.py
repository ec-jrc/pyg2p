__author__ = 'dominik'

import collections
from util.logger.Logger import Logger
import gribpcraster.application.ExecutionContext as ex

class Messages():

    def __init__(self, values_, missing_, unit_, type_of_level_, type_of_step_, grid_details_, val_2nd=None, has_2_timestep_= False):
        self._logger = Logger('Messages', loggingLevel=ex.global_logger_level)
        self._all_values = {}
        self.values_second_res = {}
        self.type_of_step=type_of_step_
        self.type_of_level=type_of_level_
        self.unit=unit_
        self.missing_value = missing_
        self._has_2_timestep = has_2_timestep_
        #print self._has_2_timestep
        #print values_

        #order the dict in endStep ascending (key is 'startStep-endStep-resolution')

        #raw_input('ecco')
        #sss= sorted(values_.iteritems(), key=lambda (k, v): (int(k.end_step), v))
        #print sss
        #for k,v in values_.iteritems():
        #    if k.end_step==0:
        #        raw_input('ecco')
        #        print v
            #raw_input('ecco')

        od = collections.OrderedDict(sorted(values_.iteritems(), key=lambda (k, v): (int(k.end_step), v)))
        self.values_first_or_single_res = od
        self._all_values.update(od)
        if val_2nd is not None:
            od = collections.OrderedDict(sorted(val_2nd.items(), key = lambda (k,v) : (int(k.end_step), v)))
            self.values_second_res = od
            self._all_values.update(od)

        self.grid_details =grid_details_
        # #order the key list and log the first element
        self.first_step_range = sorted(self._all_values.keys(), key = lambda k : (int(k.end_step)))[0]
        # self._log('First message has: '+str(self.first_step_range))
        # for k in sorted(self._all_values.keys(), key = lambda k : (int(k.end_step))):
        #     self._log(' message has: '+str(k))

    def append_2nd_res_messages(self, messages):
        #messages is a Messages object
        self.grid_details.set_2nd_resolution(messages.grid_details, messages.first_step_range)
        od =  collections.OrderedDict(sorted(messages.getValuesOfFirstOrSingleRes().items(), key = lambda (k,v) : (int(k.end_step),v)))
        self.values_second_res = od
        self._all_values.update(self.values_second_res)
        #garbaged
        messages = None

    def getUnit(self):
        return self.unit

    def getValuesOfFirstOrSingleRes(self):
        od =  collections.OrderedDict(sorted(self.values_first_or_single_res.items(), key = lambda (k,v) : (int(k.end_step),v)))
        return od

    def getValuesOfSecondRes(self):
        od =  collections.OrderedDict(sorted(self.values_second_res.items(), key = lambda (k,v) : (int(k.end_step),v)))
        return od

    def getGridId(self):
        return self.grid_details.getGridId()

    def getGridId2(self):
        return self.grid_details.get_2nd_resolution().getGridId()

    def getTypeOfStep(self):
        return self.type_of_step

    def getTypeOfLevel(self):
        return self.type_of_level

    def getGridType(self):
        return self.grid_details.getGridType()

    def getValues(self, step):
        return self.values_first_or_single_res[step]

    def getLatLons(self):
        return self.grid_details.getLatLons()

    def getLatLons2(self):
        return self.grid_details.get_2nd_resolution().getLatLons()

    def getMissingValue(self):
        return self.missing_value

    def getGridDetails(self):
        return self.grid_details

    def getGridDetails2nd(self):
        return self.grid_details.get_2nd_resolution()

    def change_resolution(self):
        return self.grid_details.get_2nd_resolution() is not None

    def change_time_resolution(self):
        #returns boolean
        return self._has_2_timestep

    def getValuesByTimeRes(self, input_step):
        self._log('Filtering with %d'%input_step)
        dict_new = self._all_values.copy()
        dict_new = dict((key,value) for key, value in dict_new.iteritems() if key.input_step == str(input_step))
        od = collections.OrderedDict(sorted(dict_new.items(), key = lambda (k,v): (int(k.end_step), v)))
        return od

    def get_change_res_step(self):
        return self.grid_details.get_change_res_step()

    def __str__(self):
        mess = '\n\Message: \n'
        return mess

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def convertValues(self, converter):
        converter.setUnitToConvert(self.getUnit())
        converter.setMissingValue(self.getMissingValue())

        #convert all values
        self._log(converter, 'INFO')
        self._all_values = dict((key, converter.convert(values)) for (key, values) in self._all_values.iteritems())
        self.values_first_or_single_res = dict((key, converter.convert(values)) for (key, values) in self.values_first_or_single_res.iteritems())
        self.values_second_res = dict((key, converter.convert(values)) for (key, values) in self.values_second_res.iteritems())


        # for key, value in self._all_values.iteritems():

