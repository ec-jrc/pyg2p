import gc
import logging
from datetime import datetime

from pyg2p import Loggable


class Messages(Loggable):

    def __init__(self, values, mv, unit, type_of_level, type_of_step, grid_details, val_2nd=None, data_date=None):
        super().__init__()
        self.values_first_or_single_res = values
        self.values_second_res = val_2nd or {}
        self.type_of_step = type_of_step
        self.type_of_level = type_of_level
        self.unit = unit
        self.missing_value = mv
        self.data_date = datetime.strptime(str(data_date), '%Y%m%d')

        self.grid_details = grid_details
        # order key list to get first step
        self.first_step_range = sorted(self.values_first_or_single_res.keys(), key=lambda k: (int(k.end_step)))[0]

    def append_2nd_res_messages(self, messages):
        # messages is a Messages object from second set at different resolution
        self.grid_details.set_2nd_resolution(messages.grid_details, messages.first_step_range)
        self.values_second_res = messages.first_resolution_values()

    def first_resolution_values(self):
        return self.values_first_or_single_res

    def second_resolution_values(self):
        return self.values_second_res

    @property
    def grid_id(self):
        return self.grid_details.grid_id

    @property
    def grid2_id(self):
        return self.grid_details.get_2nd_resolution().grid_id

    @property
    def latlons(self):
        return self.grid_details.latlons

    @property
    def latlons_2nd(self):
        second_res_grid = self.grid_details.get_2nd_resolution()
        if second_res_grid:
            return second_res_grid.latlons
        return None, None

    def have_resolution_change(self):
        return self.grid_details.get_2nd_resolution() is not None

    def change_resolution_step(self):
        return self.grid_details.get_change_res_step()

    def apply_conversion(self, converter):
        converter.set_unit_to_convert(self.unit)
        converter.set_missing_value(self.missing_value)
        # convert all values
        self._log(converter, 'INFO')
        self.values_first_or_single_res = {key: converter.convert(values) for key, values in self.values_first_or_single_res.items()}
        self.values_second_res = {key: converter.convert(values) for key, values in self.values_second_res.items()}
        gc.collect()

    def __len__(self):
        return len(self.values_first_or_single_res) + len(self.values_second_res)
