import gc
import logging
from collections import namedtuple
from datetime import datetime

import eccodes
import os
current_dir = os.path.dirname(os.path.abspath(__file__))

version_file = os.path.join(current_dir, 'VERSION')
if not os.path.exists(version_file):
    version_file = os.path.join(current_dir, '../../VERSION')

with open(version_file, 'r') as f:
    version = f.read().strip()

__version__ = version
__authors__ = "Domenico Nappo"


class Loggable:

    def __init__(self):
        self._logger = logging.getLogger()

    def _log(self, message, level='DEBUG'):
        self._logger.log(logging._checkLevel(level), message)


class Step:
    def __init__(self, start_step, end_step, points_meridian, input_step, level):
        self.start_step = start_step
        self.end_step = end_step
        # spatial resolution - pointsAlongMeridian in GRIB
        self.resolution = points_meridian
        # temporal resolution
        self.input_step = input_step
        self.level = level

    def __hash__(self):
        return hash((self.start_step, self.end_step, self.resolution, self.input_step, self.level))

    def __eq__(self, other):
        return (self.start_step, self.end_step, self.resolution, self.input_step, self.level) == (
               (other.start_step, other.end_step, other.resolution, other.input_step, other.level))

    def __repr__(self):
        return f's:{self.start_step} e:{self.end_step} res:{self.resolution} step-lenght:{self.input_step} level:{self.level}'

    def __lt__(self, other):
        return self.start_step < other.start_step

    def __le__(self, other):
        return self.start_step <= other.start_step


GRIBInfo = namedtuple('GRIBInfo', 'input_step, input_step2, change_step_at, type_of_param, start, end, mv')


class GribGridDetails(Loggable):
    """
    # Managed grid types:
        * regular_gg, regular_ll
        * reduced_ll, reduced_gg (include octahedral grid)
        * rotated_ll, rotated_gg

    """

    keys = (('gridType', 'string'), ('radius', 'double'), ('numberOfValues', 'long'),
            ('Ni', 'long'), ('Nj', 'long'), ('missingValue', 'double'),
            ('longitudeOfFirstGridPointInDegrees', 'double'), ('longitudeOfLastGridPointInDegrees', 'double'),
            ('latitudeOfSouthernPoleInDegrees', 'double'), ('longitudeOfSouthernPoleInDegrees', 'double'),
            ('angleOfRotationInDegrees', 'double'))
    check_for_missing_keys = ('Ni', 'Nj', 'longitudeOfLastGridPointInDegrees')

    def __init__(self, gid):

        super().__init__()
        self._gid = gid
        self._geo_keys = {
            key_: getattr(eccodes, f'codes_get_{type_}')(gid, key_)
            for key_, type_ in self.keys
            if eccodes.codes_is_defined(gid, key_)
        }
        self._missing_keys = {}
        for key_ in self.check_for_missing_keys:
            try:
                if eccodes.codes_is_missing(gid, key_):
                    self._missing_keys[key_] = 'MISSING'
            except eccodes.KeyValueNotFoundError:
                self._missing_keys[key_] = 'MISSING'

        self._grid_type = self._geo_keys.get('gridType')
        self._points_meridian = self._geo_keys.get('Nj')
        self._missing_value = self._geo_keys.get('missingValue')
        self.grid_id = self._build_id()
        # lazy computation
        self._lats = None
        self._longs = None

        self._grid_details_2nd = None
        self._change_resolution_step = None

    def _build_id(self):
        ni = 'M' if 'Ni' in self._missing_keys else self._geo_keys.get('Ni')
        nj = 'M' if 'Nj' in self._missing_keys else self._geo_keys.get('Nj')
        num_of_values = self._geo_keys.get('numberOfValues')
        long_first = ('%.4f' % (self._geo_keys.get('longitudeOfFirstGridPointInDegrees'),)).rstrip('0').rstrip('.')
        long_last = 'M' if 'longitudeOfLastGridPointInDegrees' in self._missing_keys else ('%.4f' % (self._geo_keys.get('longitudeOfLastGridPointInDegrees'),)).rstrip('0').rstrip('.')
        grid_id = f'{long_first}${long_last}${ni}${nj}${num_of_values}${self._grid_type}'
        return grid_id

    def set_2nd_resolution(self, grid2nd, step_range_):
        self._log(f'Grib resolution changes at key {step_range_}')
        self._grid_details_2nd = grid2nd
        self._change_resolution_step = step_range_
        # change of points along meridian!
        self._points_meridian = grid2nd.num_points_along_meridian

    def get_2nd_resolution(self):
        return self._grid_details_2nd

    def get_change_res_step(self):
        return self._change_resolution_step

    @property
    def latlons(self):
        # this method is called only for scipy interpolation
        if self._lats is None:
            self._log('Fetching coordinates from grib file')
            self._lats = eccodes.codes_get_double_array(self._gid, 'latitudes')
            self._longs = eccodes.codes_get_double_array(self._gid, 'longitudes')
        return self._lats, self._longs

    @property
    def num_points_along_meridian(self):
        return self._points_meridian

    def get(self, geo_key):
        return self._geo_keys[geo_key]

    def __str__(self):
        return str(self._geo_keys)


class Messages(Loggable):

    def __init__(self, values, mv, unit, type_of_level, type_of_step, step_units, grid_details, val_2nd=None, data_date=None, data_time='0'):
        super().__init__()
        self.values_first_or_single_res = values
        self.values_second_res = val_2nd or {}
        self.step_type = type_of_step
        self.step_units = step_units
        self.type_of_level = type_of_level
        self.unit = unit
        self.missing_value = mv
        self.data_date = datetime.strptime(f'{data_date}{data_time}', '%Y%m%d%H')

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
