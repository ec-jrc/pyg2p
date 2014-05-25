__author__ = 'dominik'

import collections
from util.logger.Logger import Logger
import gribpcraster.application.ExecutionContext as ex
import gc


class Messages():

    def __init__(self, values_, missing_, unit_, type_of_level_, type_of_step_, grid_details_, val_2nd=None, has_2_timestep=False):
        self._logger = Logger('Messages', loggingLevel=ex.global_logger_level)
        # self._all_values = {}
        self.values_first_or_single_res = collections.OrderedDict(sorted(values_.iteritems(), key=lambda (k, v): (int(k.end_step), v)))
        self.values_second_res = {}
        self.type_of_step = type_of_step_
        self.type_of_level = type_of_level_
        self.unit = unit_
        self.missing_value = missing_
        self._has_2_timestep = has_2_timestep


        # self._all_values.update(od)
        if val_2nd is not None:
            self.values_second_res = collections.OrderedDict(sorted(val_2nd.iteritems(), key=lambda (k, v): (int(k.end_step), v)))
            # self._all_values.update(od)

        self.grid_details = grid_details_
        # #order the key list
        self.first_step_range = sorted(self.values_first_or_single_res.keys(), key=lambda k: (int(k.end_step)))[0]

    def append_2nd_res_messages(self, messages):
        #messages is a Messages object
        self.grid_details.set_2nd_resolution(messages.grid_details, messages.first_step_range)
        self.values_second_res = collections.OrderedDict(sorted(messages.getValuesOfFirstOrSingleRes().iteritems(), key=lambda (k, v): (int(k.end_step), v)))
        # self._all_values.update(self.values_second_res)
        #garbaged
        del messages

    def getUnit(self):
        return self.unit

    def getValuesOfFirstOrSingleRes(self):
        # od = collections.OrderedDict(sorted(self.values_first_or_single_res.items(), key=lambda (k, v): (int(k.end_step), v)))
        # return od
        return self.values_first_or_single_res

    def getValuesOfSecondRes(self):
        return self.values_second_res

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

    def have_change_resolution(self):
        return self.grid_details.get_2nd_resolution() is not None

    def change_time_resolution(self):
        #returns boolean
        return self._has_2_timestep

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
        # self._all_values = dict((key, converter.convert(values)) for (key, values) in self._all_values.iteritems())
        self.values_first_or_single_res = {key: converter.convert(values) for key, values in self.values_first_or_single_res.iteritems()}
        self.values_second_res = {key: converter.convert(values) for key, values in self.values_second_res.iteritems()}
        gc.collect()
