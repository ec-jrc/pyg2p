import gribapi as GRIB
import os
from gribpcraster.exc.ApplicationException import NO_MESSAGES
from gribpcraster.application.domain.GribGridDetails import GribGridDetails
from gribpcraster.application.domain.Messages import Messages
from util.logger.Logger import Logger
from gribpcraster.exc.ApplicationException import ApplicationException
from gribpcraster.application.domain.Key import Key
import util.generics as utils
import gribpcraster.application.ExecutionContext as ex


def get_id(grib_file, reader_args):
    reader = GRIBReader(grib_file)
    gribs_for_id = reader._get_gids(**reader_args)
    grid = GribGridDetails(gribs_for_id[0])
    return grid.getGridId()


class GRIBReader(object):

    def __init__(self, grib_file, w_perturb=False):
        GRIB.grib_no_fail_on_wrong_length(True)
        self._grib_file = os.path.abspath(grib_file)
        self._file_handler = None
        self._grbindx = None
        self._logger = Logger('GRIBReader', loggingLevel=ex.global_logger_level)
        self._log("Opening the GRIBReader for " + self._grib_file)

        try:
            index_keys = ['shortName']
            if w_perturb:
                index_keys.append('perturbationNumber')
            self._grbindx = GRIB.grib_index_new_from_file(str(self._grib_file), index_keys)  #open(self._grib_file)
        except GRIB.GribInternalError:
            self._log("Can't use index on {}".format(self._grib_file), 'WARN')
            self._file_handler = open(self._grib_file)
        self._selected_grbs = []
        self._mv = -1
        self._step_grib = -1
        self._step_grib2 = -1
        self._change_step_at = ''
        self._gid_main_res = None
        self._gid_ext_res = None

    @staticmethod
    def _find(gid, **kwargs):
        for k, v in kwargs.iteritems():
            # if k in ['shortName', 'perturbationNumber']: continue
            if not GRIB.grib_is_defined(gid, k): return False
            # is v a "container-like" non-string object?
            iscontainer = utils.is_container(v)
            # is v callable?
            iscallable = utils.is_callable(v)
            if not iscontainer and not iscallable and GRIB.grib_get(gid, k) == v: continue
            elif iscontainer and GRIB.grib_get(gid, k) in v: continue  # v is a list.
            elif iscallable and v(GRIB.grib_get(gid, k)): continue  # v a boolean function
            else: return False
        return True


    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)


    def close(self):
        self._log("Closing " + self._grib_file)
        for g in self._selected_grbs:
            GRIB.grib_release(g)
        self._selected_grbs = None
        if self._grbindx:
            GRIB.grib_index_release(self._grbindx)
            self._grbindx = None
        if self._file_handler:
            self._file_handler.close()
            self._file_handler = None
        self._logger.close()

    #returns an array of GRIB selected messages as gribmessage objects

    def scan_grib(self, gribs, kwargs):
        v_selected = kwargs['shortName']
        v_pert = kwargs.get('perturbationNumber', -1)
        if not utils.is_container(v_selected):
            v_selected = [v_selected]
        if self._grbindx:
            for v in v_selected:
                GRIB.grib_index_select(self._grbindx, 'shortName', str(v))
                if v_pert != -1:
                    GRIB.grib_index_select(self._grbindx, 'perturbationNumber', int(v_pert))
                while 1:
                    gid = GRIB.grib_new_from_index(self._grbindx)
                    if gid is None: break
                    if GRIBReader._find(gid, **kwargs):
                        gribs.append(gid)
                    else:
                        #release the unused grib
                        GRIB.grib_release(gid)
        elif self._file_handler:
            while 1:
                    gid = GRIB.grib_new_from_file(self._file_handler)
                    if gid is None: break
                    if GRIBReader._find(gid, **kwargs):
                        gribs.append(gid)
                    else:
                        #release the unused grib
                        GRIB.grib_release(gid)

    def _get_gids(self, **kwargs):
        gribs = []
        try:
            self.scan_grib(gribs, kwargs)
            if (len(gribs) == 0) and ('startStep' in kwargs and hasattr(kwargs['startStep'], '__call__') and not kwargs['startStep'](0)):
                kwargs['startStep'] = lambda s: s >= 0
                self.scan_grib(gribs, kwargs)
            return gribs
        except ValueError, noValsExc:
            raise ApplicationException.get_programmatic_exc(NO_MESSAGES, details="using "+str(kwargs))

    def getSelectedMessages(self, **kwargs):
        #concrete override
        self._selected_grbs = self._get_gids(**kwargs)
        self._log("Selected " + str(len(self._selected_grbs)) + " grib messages")

        if len(self._selected_grbs) > 0:
            self._gid_main_res = self._selected_grbs[0]
            grid = GribGridDetails(self._selected_grbs[0])

            #some cumulated messages come with the message at step=0 as instant, to permit aggregation
                #cumulated rainfall rates could have the step zero instant message as kg/m^2, instead of kg/(m^2*s)
            if len(self._selected_grbs) > 1:
                unit = GRIB.grib_get(self._selected_grbs[1], 'units')
                type_of_step = GRIB.grib_get(self._selected_grbs[1], 'stepType')
            else:
                type_of_step = GRIB.grib_get(self._selected_grbs[0], 'stepType')
                unit = GRIB.grib_get(self._selected_grbs[0], 'units')
            short_name = GRIB.grib_get(self._selected_grbs[0], 'shortName')
            type_of_level = GRIB.grib_get(self._selected_grbs[0], 'levelType')

            # if len(self._selected_grbs) > 1:
            #
            #     if unit != GRIB.grib_get(self._selected_grbs[1], 'units'):
            #         unit = GRIB.grib_get(self._selected_grbs[1], 'units')

            missing_value = GRIB.grib_get(self._selected_grbs[0], 'missingValue')
            allValues = {}
            allValues2ndRes = {}
            grid2 = None
            input_step = self._step_grib
            for g in self._selected_grbs:

                start_step = GRIB.grib_get(g, 'startStep')
                end_step = GRIB.grib_get(g, 'endStep')
                points_meridian = GRIB.grib_get(g, 'Nj')

                if str(start_step) + '-' + str(end_step) == self._change_step_at:
                    #second time resolution
                    input_step = self._step_grib2

                key = Key(start_step, end_step, points_meridian, input_step)
                if points_meridian != grid.getNumberOfPointsAlongMeridian() and grid.get_2nd_resolution() is None:
                    #found second resolution messages
                    grid2 = GribGridDetails(g)
                    self._gid_ext_res = g

                values = GRIB.grib_get_double_array(g, 'values')  # .astype(np.float32, copy=False)
                if grid2 is None:
                    allValues[key] = values
                elif points_meridian != grid.getNumberOfPointsAlongMeridian():
                    allValues2ndRes[key] = values

            if grid2 is not None:
                key_2nd_spatial_res = min(allValues2ndRes.keys())
                grid.set_2nd_resolution(grid2, key_2nd_spatial_res)
            second_time_res = self._step_grib2 != -1
            return Messages(allValues, missing_value, unit,
                            type_of_level, type_of_step, grid, allValues2ndRes,
                            has_2_timestep=second_time_res), short_name
        #no messages found
        else:
            raise ApplicationException.get_programmatic_exc(3000, details="using "+str(kwargs))

    #return input_step, type_of_step
    @staticmethod
    def _find_start_end_steps(gribs):

        start_steps = [GRIB.grib_get(gribs[i], 'startStep') for i in xrange(len(gribs))]
        end_steps = [GRIB.grib_get(gribs[i], 'endStep') for i in xrange(len(gribs))]
        start_grib = min(start_steps)
        end_grib = max(end_steps)
        ord_end_steps = sorted(end_steps)
        ord_start_steps = sorted(start_steps)
        step = ord_end_steps[1] - ord_end_steps[0]
        step2 = -1
        change_step_at = ''
        for i in xrange(2, len(ord_end_steps)):
            if step2 == -1 and ord_end_steps[i] - ord_end_steps[i - 1] != step:
                step2 = ord_end_steps[i] - ord_end_steps[i - 1]
                change_step_at = str(ord_start_steps[i]) + '-' + str(ord_end_steps[i])
        return start_grib, end_grib, step, step2, change_step_at


    def get_grib_info(self, readerArgs):
        _gribs_for_utils = self._get_gids(**readerArgs)
        if len(_gribs_for_utils) > 0:
            radius = GRIB.grib_get(_gribs_for_utils[0], 'radius')
            type_of_step = GRIB.grib_get(_gribs_for_utils[1], 'stepType')  # instant,avg,cumul
            self._mv = GRIB.grib_get_double(_gribs_for_utils[0], 'missingValue')
            start_grib, end_grib, self._step_grib, self._step_grib2, self._change_step_at = self._find_start_end_steps(_gribs_for_utils)
            self._log("Grib input step %d [type of step: %s]" % (self._step_grib, type_of_step))
            self._log('Gribs from %d to %d' % (start_grib, end_grib))
            for g in _gribs_for_utils:
                GRIB.grib_release(g)
            _gribs_for_utils = None
            import gc
            gc.collect()
            return radius, self._step_grib, self._step_grib2, self._change_step_at, type_of_step, start_grib, end_grib, self._mv
        #no messages found
        else:
            raise ApplicationException.get_programmatic_exc(3000, details="using " + str(readerArgs))

    def get_gids_for_grib_intertable(self):
        #returns gids of messages to use to create interpolation tables
        val = GRIB.grib_get_double_array(self._gid_main_res, 'values')
        val2 = None
        if self._gid_ext_res:
            val2 = GRIB.grib_get_double_array(self._gid_ext_res, 'values')
        return self._gid_main_res, val, self._gid_ext_res, val2

    def set_2nd_aux(self, aux_2nd_gid):
        #injecting the second spatial resolution gid
        self._gid_ext_res = aux_2nd_gid

    def get_main_aux(self):
        return self._gid_main_res