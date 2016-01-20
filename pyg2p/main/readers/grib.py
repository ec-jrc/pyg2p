import os

from gribapi import (grib_no_fail_on_wrong_length, grib_is_defined,
                     grib_index_new_from_file, grib_new_from_index, grib_new_from_file, grib_index_select,
                     grib_index_release, grib_release,
                     grib_get, grib_get_double_array, grib_get_double,
                     GribInternalError,)
from pyg2p.main.domain.grid_details import GribGridDetails
from pyg2p.main.domain.messages import Messages
from pyg2p.main.domain.step import Step

from pyg2p.util import generics as utils
from pyg2p.main.exceptions import ApplicationException, NO_MESSAGES
from pyg2p.util.logger import Logger


class GRIBInfo(object):
    def __init__(self, **kwargs):
        self.input_step = kwargs.get('input_step')
        self.input_step2 = kwargs.get('input_step2')
        self.change_step_at = kwargs.get('change_step_at')
        self.type_of_param = kwargs.get('type_of_param')
        self.start = kwargs.get('start')
        self.end = kwargs.get('end')
        self.mv = kwargs.get('mv')


class GRIBReader(object):

    def __init__(self, grib_file, w_perturb=False):
        grib_no_fail_on_wrong_length(True)
        self._grib_file = os.path.abspath(grib_file)
        self._file_handler = None
        self._grbindx = None
        self._logger = Logger.get_logger()
        self._log('Opening GRIBReader for {}'.format(self._grib_file))

        try:
            index_keys = ['shortName']
            if w_perturb:
                index_keys.append('perturbationNumber')
            self._grbindx = grib_index_new_from_file(str(self._grib_file), index_keys)  #open(self._grib_file)
        except GribInternalError:
            self._log("Can't use index on {}".format(self._grib_file), 'WARN')
            self._file_handler = open(self._grib_file)
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
        for k, v in kwargs.iteritems():
            if not grib_is_defined(gid, k):
                return False
            iscontainer = utils.is_container(v)
            iscallable = utils.is_callable(v)
            if (not iscontainer and not iscallable and grib_get(gid, k) == v) or\
                    (iscontainer and grib_get(gid, k) in v) or \
                    (iscallable and v(grib_get(gid, k))):
                continue
            else:
                return False
        return True

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def close(self):
        self._log('Closing gribs messages from {}'.format(self._grib_file))
        for g in self._selected_grbs:
            grib_release(g)
        self._selected_grbs = None
        if self._grbindx:
            grib_index_release(self._grbindx)
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
                grib_index_select(self._grbindx, 'shortName', str(v))
                while 1:
                    gid = grib_new_from_index(self._grbindx)
                    if gid is None:
                        break
                    has_geo = True
                    grib_release(gid)

        elif self._file_handler:
            while 1:
                gid = grib_new_from_file(self._file_handler)
                if gid is None:
                    break
                has_geo = True
                grib_release(gid)
        return has_geo

    def scan_grib(self, gribs, kwargs):
        v_selected = kwargs['shortName']
        v_pert = kwargs.get('perturbationNumber', -1)
        grib_append = gribs.append
        if not utils.is_container(v_selected):
            v_selected = [v_selected]
        if self._grbindx:
            for v in v_selected:
                grib_index_select(self._grbindx, 'shortName', str(v))
                if v_pert != -1:
                    grib_index_select(self._grbindx, 'perturbationNumber', int(v_pert))
                while 1:
                    gid = grib_new_from_index(self._grbindx)
                    if gid is None:
                        break
                    if GRIBReader._find(gid, **kwargs):
                        grib_append(gid)
                    else:
                        # release unused grib
                        grib_release(gid)
        elif self._file_handler:
            while 1:
                gid = grib_new_from_file(self._file_handler)
                if gid is None:
                    break
                if GRIBReader._find(gid, **kwargs):
                    grib_append(gid)
                else:
                    # release unused grib
                    grib_release(gid)

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
                unit = grib_get(self._selected_grbs[1], 'units')
                type_of_step = grib_get(self._selected_grbs[1], 'stepType')
            else:
                type_of_step = grib_get(self._selected_grbs[0], 'stepType')
                unit = grib_get(self._selected_grbs[0], 'units')
            short_name = grib_get(self._selected_grbs[0], 'shortName')
            type_of_level = grib_get(self._selected_grbs[0], 'levelType')

            missing_value = grib_get(self._selected_grbs[0], 'missingValue')
            all_values = {}
            all_values_second_res = {}
            grid2 = None
            input_step = self._step_grib
            for g in self._selected_grbs:

                start_step = grib_get(g, 'startStep')
                end_step = grib_get(g, 'endStep')
                points_meridian = grib_get(g, 'Nj')
                if '{}-{}'.format(start_step, end_step) == self._change_step_at:
                    # second time resolution
                    input_step = self._step_grib2

                key = Step(start_step, end_step, points_meridian, input_step)

                if points_meridian != grid.num_points_along_meridian and grid.get_2nd_resolution() is None:
                    # found second resolution messages
                    grid2 = GribGridDetails(g)
                    self._gid_ext_res = g

                values = grib_get_double_array(g, 'values')
                if not grid2:
                    all_values[key] = values
                elif points_meridian != grid.num_points_along_meridian:
                    all_values_second_res[key] = values

            if grid2:
                key_2nd_spatial_res = min(all_values_second_res.keys())
                grid.set_2nd_resolution(grid2, key_2nd_spatial_res)
            return Messages(all_values, missing_value, unit, type_of_level, type_of_step, grid, all_values_second_res), short_name
        # no messages found
        else:
            raise ApplicationException.get_exc(3000, details="using {}".format(kwargs))

    @staticmethod
    def _find_start_end_steps(gribs):
        # return input_steps,
        # change step if a second time resolution is found

        start_steps = [grib_get(gribs[i], 'startStep') for i in xrange(len(gribs))]
        end_steps = [grib_get(gribs[i], 'endStep') for i in xrange(len(gribs))]
        start_grib = min(start_steps)
        end_grib = max(end_steps)
        ord_end_steps = sorted(end_steps)
        ord_start_steps = sorted(start_steps)
        step = ord_end_steps[1] - ord_end_steps[0]
        step2 = -1
        change_step_at = ''
        for i in xrange(2, len(ord_end_steps)):
            if step2 == -1 and ord_end_steps[i] - ord_end_steps[i - 1] != step:
                # change of time resolution
                step2 = ord_end_steps[i] - ord_end_steps[i - 1]
                change_step_at = '{}-{}'.format(ord_start_steps[i], ord_end_steps[i])
        return start_grib, end_grib, step, step2, change_step_at

    def get_grib_info(self, select_args):
        _gribs_for_utils = self._get_gids(**select_args)
        if len(_gribs_for_utils) > 0:
            type_of_step = grib_get(_gribs_for_utils[1], 'stepType')  # instant, avg, cumul
            self._mv = grib_get_double(_gribs_for_utils[0], 'missingValue')
            start_grib, end_grib, self._step_grib, self._step_grib2, self._change_step_at = self._find_start_end_steps(_gribs_for_utils)
            self._log("Grib input step %d [type of step: %s]" % (self._step_grib, type_of_step))
            self._log('Gribs from %d to %d' % (start_grib, end_grib))
            for g in _gribs_for_utils:
                grib_release(g)
            _gribs_for_utils = None
            del _gribs_for_utils
            import gc
            gc.collect()
            info = GRIBInfo(input_step=self._step_grib, input_step2=self._step_grib2,
                            change_step_at=self._change_step_at, type_of_param=type_of_step,
                            start=start_grib, end=end_grib, mv=self._mv)
            return info
        # no messages found
        else:
            raise ApplicationException.get_exc(3000, details="using " + str(select_args))

    def get_gids_for_grib_intertable(self):
        # returns gids of messages to use to create interpolation tables
        val = grib_get_double_array(self._gid_main_res, 'values')
        val2 = None
        if self._gid_ext_res:
            val2 = grib_get_double_array(self._gid_ext_res, 'values')
        return self._gid_main_res, val, self._gid_ext_res, val2

    def set_2nd_aux(self, aux_2nd_gid):
        # injecting the second spatial resolution gid
        self._gid_ext_res = aux_2nd_gid

    def get_main_aux(self):
        return self._gid_main_res
