from util.logger import Logger
import gc


class Messages(object):

    def __init__(self, values_, missing_, unit_, type_of_level_, type_of_step_, grid_details_, val_2nd=None):
        self._logger = Logger.get_logger()
        self.values_first_or_single_res = values_
        self.values_second_res = val_2nd or {}
        self.type_of_step = type_of_step_
        self.type_of_level = type_of_level_
        self.unit = unit_
        self.missing_value = missing_

        self.grid_details = grid_details_
        # order key list to get first step
        self.first_step_range = sorted(self.values_first_or_single_res.keys(), key=lambda k: (int(k.end_step)))[0]

    def append_2nd_res_messages(self, messages):
        # messages is a Messages object from second set at different resolution
        self.grid_details.set_2nd_resolution(messages.grid_details, messages.first_step_range)
        self.values_second_res = messages.getValuesOfFirstOrSingleRes()
        # garbaged
        messages = None
        del messages

    def getUnit(self):
        return self.unit

    def getValuesOfFirstOrSingleRes(self):
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

    def get_change_res_step(self):
        return self.grid_details.get_change_res_step()

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def convertValues(self, converter):
        converter.setUnitToConvert(self.getUnit())
        converter.setMissingValue(self.getMissingValue())
        # convert all values
        self._log(converter, 'INFO')
        self.values_first_or_single_res = {key: converter.convert(values) for key, values in self.values_first_or_single_res.iteritems()}
        self.values_second_res = {key: converter.convert(values) for key, values in self.values_second_res.iteritems()}
        gc.collect()
