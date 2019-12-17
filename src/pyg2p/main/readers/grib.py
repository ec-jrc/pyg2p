import os
import logging
from collections import namedtuple

from eccodes import (codes_no_fail_on_wrong_length, codes_is_defined,
                     codes_index_new_from_file, codes_new_from_index, codes_new_from_file, codes_index_select,
                     codes_index_release, codes_release,
                     codes_get, codes_get_double_array, codes_get_double,
                     GribInternalError, codes_get_array, CODES_PRODUCT_GRIB)
from numpy import ma

from ..domain.grid_details import GribGridDetails
from ..domain.messages import Messages
from ..domain.step import Step

from pyg2p.util import generics as utils
from pyg2p.main.exceptions import ApplicationException, NO_MESSAGES
from pyg2p import Loggable

GRIBInfo = namedtuple('GRIBInfo', 'input_step, input_step2, change_step_at, type_of_param, start, end, mv')


class GRIBReader(Loggable):

    def __init__(self, grib_file, w_perturb=False):
        # codes_no_fail_on_wrong_length(True)
        super().__init__()
        self._grib_file = os.path.abspath(grib_file)
        self._file_handler = None
        self._grbindx = None
        self._logger = logging.getLogger()
        self._log('Opening GRIBReader for {}'.format(self._grib_file))

        try:
            index_keys = ['shortName']
            if w_perturb:
                index_keys.append('perturbationNumber')
            self._grbindx = codes_index_new_from_file(str(self._grib_file), index_keys)
        except GribInternalError:
            self._log("Can't use index on {}".format(self._grib_file), 'WARN')
            self._file_handler = open(self._grib_file, 'rb')
        self._selected_grbs = []
        self._mv = -1
        self._step_grib = -1
        self._step_grib2 = -1
        self._change_step_at = ''
        self._gid_main_res = None
        self._gid_ext_res = None

    @classmethod
    def get_id(cls, grib_file, reader_args):
        reader = GRIBReader(grib_file)
        gribs_for_id = reader._get_gids(**reader_args)
        grid = GribGridDetails(gribs_for_id[0])
        reader.close()
        return grid.grid_id

    @staticmethod
    def _find(gid, **kwargs):
        for k, v in kwargs.items():
            if not codes_is_defined(gid, k):
                return False
            iscontainer = utils.is_container(v)
            iscallable = utils.is_callable(v)
            if (not iscontainer and not iscallable and codes_get(gid, k) == v) or\
                    (iscontainer and codes_get(gid, k) in v) or \
                    (iscallable and v(codes_get(gid, k))):
                continue
            else:
                return False
        return True

    def close(self):
        self._log('Closing gribs messages from {}'.format(self._grib_file))
        for g in self._selected_grbs:
            codes_release(g)
        self._selected_grbs = None
        if self._grbindx:
            codes_index_release(self._grbindx)
            self._grbindx = None
        if self._file_handler:
            self._file_handler.close()
            self._file_handler = None

    def has_geopotential(self):
        has_geo = False
        from pyg2p.main.config import GeopotentialsConfiguration
        v_selected = GeopotentialsConfiguration.short_names
        if self._grbindx:
            for v in v_selected:
                codes_index_select(self._grbindx, 'shortName', str(v))
                while 1:
                    gid = codes_new_from_index(self._grbindx)
                    if gid is None:
                        break
                    has_geo = True
                    codes_release(gid)

        elif self._file_handler:
            while 1:
                gid = codes_new_from_file(self._file_handler, product_kind=CODES_PRODUCT_GRIB)
                if gid is None:
                    break
                has_geo = True
                codes_release(gid)
        return has_geo

    def scan_grib(self, gribs, kwargs):
        v_selected = kwargs['shortName']
        v_pert = kwargs.get('perturbationNumber', -1)
        if not utils.is_container(v_selected):
            v_selected = [v_selected]
        if self._grbindx:
            for v in v_selected:
                codes_index_select(self._grbindx, 'shortName', str(v))
                if v_pert != -1:
                    codes_index_select(self._grbindx, 'perturbationNumber', int(v_pert))
                while 1:
                    gid = codes_new_from_index(self._grbindx)
                    if gid is None:
                        break
                    if GRIBReader._find(gid, **kwargs):
                        gribs.append(gid)
                    else:
                        # release unused grib
                        codes_release(gid)
        elif self._file_handler:
            while 1:
                gid = codes_new_from_file(self._file_handler, product_kind=CODES_PRODUCT_GRIB)
                if gid is None:
                    break
                if GRIBReader._find(gid, **kwargs):
                    gribs.append(gid)
                else:
                    # release unused grib
                    codes_release(gid)

    def _get_gids(self, **kwargs):
        gribs = []
        try:
            self.scan_grib(gribs, kwargs)
            if (len(gribs) == 0) and ('startStep' in kwargs and utils.is_callable(kwargs['startStep']) and not kwargs['startStep'](0)):
                kwargs['startStep'] = lambda s: s >= 0
                self.scan_grib(gribs, kwargs)
            return gribs
        except ValueError:
            raise ApplicationException.get_exc(NO_MESSAGES, details="using {}".format((str(kwargs))))

    def select_messages(self, **kwargs):
        self._selected_grbs = self._get_gids(**kwargs)
        self._log("Selected {} grib messages".format(len(self._selected_grbs)))

        if len(self._selected_grbs) > 0:
            self._gid_main_res = self._selected_grbs[0]
            grid = GribGridDetails(self._selected_grbs[0])
            # some cumulated messages come with the message at step=0 as instant, to permit aggregation
            # cumulated rainfall rates could have the step zero instant message as kg/m^2, instead of kg/(m^2*s)
            if len(self._selected_grbs) > 1:
                unit = codes_get(self._selected_grbs[1], 'units')
                type_of_step = codes_get(self._selected_grbs[1], 'stepType')
            else:
                type_of_step = codes_get(self._selected_grbs[0], 'stepType')
                unit = codes_get(self._selected_grbs[0], 'units')
            short_name = codes_get(self._selected_grbs[0], 'shortName')
            type_of_level = codes_get(self._selected_grbs[0], 'levelType')

            missing_value = codes_get(self._selected_grbs[0], 'missingValue')
            data_date = codes_get(self._selected_grbs[0], 'dataDate')
            all_values = {}
            all_values_second_res = {}
            grid2 = None
            input_step = self._step_grib
            for g in self._selected_grbs:
                start_step = codes_get(g, 'startStep')
                end_step = codes_get(g, 'endStep')
                points_meridian = codes_get(g, 'Nj')
                if '{}-{}'.format(start_step, end_step) == self._change_step_at:
                    # second time resolution
                    input_step = self._step_grib2

                step_key = Step(start_step, end_step, points_meridian, input_step)

                if points_meridian != grid.num_points_along_meridian and grid.get_2nd_resolution() is None:
                    # found second resolution messages
                    grid2 = GribGridDetails(g)
                    self._gid_ext_res = g
                values = codes_get_double_array(g, 'values')

                # Handling missing grib values.
                # If bitmap is present, array will be a masked_array
                # and array.mask will be used later
                # in interpolation and manipulation
                bitmap_present = codes_get(g, 'bitmapPresent')
                if bitmap_present:
                    # Get the bitmap array which contains 0s and 1s
                    bitmap = codes_get_array(g, 'bitmap', int)
                    values = ma.masked_where(bitmap == 0, values, copy=False)

                if not grid2:
                    all_values[step_key] = values
                elif points_meridian != grid.num_points_along_meridian:
                    all_values_second_res[step_key] = values

            if grid2:
                key_2nd_spatial_res = min(all_values_second_res.keys())
                grid.set_2nd_resolution(grid2, key_2nd_spatial_res)
            return Messages(all_values, missing_value, unit, type_of_level, type_of_step, grid, all_values_second_res, data_date=data_date), short_name
        # no messages found
        else:
            raise ApplicationException.get_exc(NO_MESSAGES, details="using {}".format(kwargs))

    @staticmethod
    def _find_start_end_steps(gribs):
        # return input_steps,
        # change step if a second time resolution is found

        start_steps = [codes_get(gribs[i], 'startStep') for i in range(len(gribs))]
        end_steps = [codes_get(gribs[i], 'endStep') for i in range(len(gribs))]
        start_grib = min(start_steps)
        end_grib = max(end_steps)
        ord_end_steps = sorted(end_steps)
        ord_start_steps = sorted(start_steps)
        if len(ord_end_steps) > 1:
            step = ord_end_steps[1] - ord_end_steps[0]
        else:
            step = ord_end_steps[0] - ord_start_steps[0]

        step2 = -1
        change_step_at = ''
        if len(ord_end_steps) > 1:
            step = ord_end_steps[1] - ord_end_steps[0]
            for i in range(2, len(ord_end_steps)):
                if step2 == -1 and ord_end_steps[i] - ord_end_steps[i - 1] != step:
                    # change of time resolution
                    step2 = ord_end_steps[i] - ord_end_steps[i - 1]
                    change_step_at = '{}-{}'.format(ord_start_steps[i], ord_end_steps[i])
        return start_grib, end_grib, step, step2, change_step_at

    def get_grib_info(self, select_args):
        _gribs_for_utils = self._get_gids(**select_args)
        if len(_gribs_for_utils) > 0:
            # instant, avg, cumul. get last stepType available because first one is sometimes misleading
            type_of_step = codes_get(_gribs_for_utils[-1], 'stepType')
            self._mv = codes_get_double(_gribs_for_utils[0], 'missingValue')
            start_grib, end_grib, self._step_grib, self._step_grib2, self._change_step_at = self._find_start_end_steps(_gribs_for_utils)
            self._log("Grib input step %d [type of step: %s]" % (self._step_grib, type_of_step))
            self._log('Gribs from %d to %d' % (start_grib, end_grib))
            for g in _gribs_for_utils:
                codes_release(g)
            _gribs_for_utils = None
            del _gribs_for_utils
            info = GRIBInfo(input_step=self._step_grib, input_step2=self._step_grib2,
                            change_step_at=self._change_step_at, type_of_param=type_of_step,
                            start=start_grib, end=end_grib, mv=self._mv)
            return info
        # no messages found
        else:
            raise ApplicationException.get_exc(NO_MESSAGES, details="using " + str(select_args))

    def get_gids_for_grib_intertable(self):
        # returns gids of messages to use to create interpolation tables
        val = codes_get_double_array(self._gid_main_res, 'values')
        val2 = None
        if self._gid_ext_res:
            val2 = codes_get_double_array(self._gid_ext_res, 'values')
        return self._gid_main_res, val, self._gid_ext_res, val2

    def set_2nd_aux(self, aux_2nd_gid):
        # injecting the second spatial resolution gid
        self._gid_ext_res = aux_2nd_gid

    def get_main_aux(self):
        return self._gid_main_res
