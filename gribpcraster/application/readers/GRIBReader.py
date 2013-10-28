import gribapi as GRIB

from gribpcraster.application.domain.GribGridDetails import GribGridDetails
from gribpcraster.application.domain.Messages import Messages
from util.logger.Logger import Logger
from gribpcraster.application.readers.IReader import IReader
from gribpcraster.exc.ApplicationException import ApplicationException
from gribpcraster.application.domain.Key import Key
import gribpcraster.application.ExecutionContext as ex

def get_id(grib_file, readerArgs):
    reader = GRIBReader(grib_file)
    gribs_for_id=reader.getGids(**readerArgs)
    grid = GribGridDetails(gribs_for_id[0])
    return grid.getGridId()




class GRIBReader(IReader):

    def __init__(self, grib_file):
        self._grib_file = grib_file
        self._logger = Logger('GRIBReader', loggingLevel=ex.global_logger_level)
        self._log("Opening the GRIBReader for "+self._grib_file)
        self._grbindx=open(self._grib_file)
        self._selected_grbs = []
        self._gribs_for_utils = []
        self._mv=-1
        self._step_grib = -1
        self._step_grib2 = -1
        self._change_step_at = ''


    @staticmethod
    def _is_stringlike(a):
        if type(a) == str or type(a) == bytes or type(a) == unicode:
            return True
        else:
            return False

    @staticmethod
    def _is_container(a):
        try: 1 in a
        except: return False
        if GRIBReader._is_stringlike(a): return False
        return True


    @staticmethod
    def _find(gid, **kwargs):

        for k, v in kwargs.items():
            if not GRIB.grib_is_defined(gid,k): return False
            # is v a "container-like" non-string object?
            iscontainer = GRIBReader._is_container(v)
            # is v callable?
            iscallable = hasattr(v, '__call__')
            if not iscontainer and not iscallable and GRIB.grib_get(gid, k) == v:
                continue
            elif iscontainer and GRIB.grib_get(gid,k) in v: # v is a list.
                continue
            elif iscallable and v(GRIB.grib_get(gid,k)): # v a boolean function
                continue
            else:
                return False
        return True

    def close(self):
        self._log("Closing "+self._grib_file)
        self._grbindx.close()
        for g in self._selected_grbs:
            GRIB.grib_release(g)
        for g in self._gribs_for_utils:
            GRIB.grib_release(g)
        self._logger.close()

    # def _log(self, message, level='DEBUG'):
    #     self._logger.log(message, level)
    #     ex.global_main_logger2Console.log(message,level)

    #returns an array of GRIB selected messages as gribmessage objects

    def getGids(self, **kwargs):

        gribs = []
        try:
            while 1:
                gid = GRIB.grib_new_from_file(self._grbindx)
                if gid is None: break
                if GRIBReader._find(gid, **kwargs):
                    gribs.append(gid)
                else:
                    #release the unused grib
                    GRIB.grib_release(gid)
            #rewind file
            self._grbindx.seek(0)

            # print kwargs['startStep'](0)
            # raw_input('f')

            if (len(gribs) == 0) and ('startStep' in kwargs and hasattr(kwargs['startStep'], '__call__') and not kwargs['startStep'](0)):
                kwargs['startStep']=lambda s:s>=0
                while 1:
                    gid = GRIB.grib_new_from_file(self._grbindx)
                    if gid is None: break
                    if GRIBReader._find(gid, **kwargs):
                        gribs.append(gid)
                    else:
                        #release the unused grib
                        GRIB.grib_release(gid)
                #rewind file
                self._grbindx.seek(0)

            return gribs

        except ValueError, noValsExc:
            raise ApplicationException.get_programmatic_exc(3000, details="using "+str(kwargs))

    def getSelectedMessages(self, **kwargs):
        #concrete override
        self._selected_grbs = self.getGids(**kwargs)
        self._log("Selected "+str(len(self._selected_grbs))+" grib messages")

        if len(self._selected_grbs) > 0:
            grid = GribGridDetails(self._selected_grbs[0])
            unit = GRIB.grib_get(self._selected_grbs[0],'units')
            type_of_step =GRIB.grib_get(self._selected_grbs[0],'stepType')
            shortName = GRIB.grib_get(self._selected_grbs[0],'shortName')
            type_of_level =GRIB.grib_get(self._selected_grbs[0],'levelType')

            if len(self._selected_grbs) > 1:
                #some cumulated messages come with the message at step=0 as instant, to permit aggregation
                #cumulated rainfall rates could have the step zero instant message as kg/m^2, instead of kg/(m^2*s)
                if unit != GRIB.grib_get(self._selected_grbs[1],'units'):
                    unit = GRIB.grib_get(self._selected_grbs[1],'units')
                if type_of_step != GRIB.grib_get(self._selected_grbs[1],'stepType'):
                    type_of_step =GRIB.grib_get(self._selected_grbs[1],'stepType')

            missing_value = GRIB.grib_get(self._selected_grbs[0],'missingValue')
            allValues = {}
            allValues2ndRes = None
            grid2 = None
            input_step = self._step_grib
            second_time_res = False
            for g in self._selected_grbs:

                start_step =GRIB.grib_get(g,'startStep')
                end_step = GRIB.grib_get(g,'endStep')
                points_meridian = GRIB.grib_get(g,'Nj')

                if str(start_step)+'-'+str(end_step) == self._change_step_at:
                    #second time resolution
                    input_step = self._step_grib2
                    second_time_res = True

                key = Key(start_step,end_step,points_meridian,input_step)

                if points_meridian != grid.getNumberOfPointsAlongMeridian() and grid.get_2nd_resolution() is None:
                    #found second resolution messages
                    grid2 = GribGridDetails(g)
                    grid.set_2nd_resolution(grid2, key)
                    points_meridian = grid2.getNumberOfPointsAlongMeridian()
                    allValues2ndRes = {}

                values = GRIB.grib_get_double_array(g,'values')
                if grid2 is None:
                    allValues[key] = values
                else:
                    allValues2ndRes[key] = values
            has_2_timestep_= self._step_grib2 != -1

            return Messages(allValues, missing_value, unit, type_of_level, type_of_step, grid, allValues2ndRes, has_2_timestep_= second_time_res), shortName
        #no messages found
        else:
            raise ApplicationException.get_programmatic_exc(3000, details="using "+str(kwargs))

    #return input_step, type_of_step
    def getStartEndAndSteps(self):
        self._log('Getting start / end steps...')
        start_steps = [GRIB.grib_get(self._gribs_for_utils[i], 'startStep') for i in range(len(self._gribs_for_utils))]
        end_steps = [GRIB.grib_get(self._gribs_for_utils[i], 'endStep') for i in range(len(self._gribs_for_utils))]
        start_grib = min(start_steps)
        end_grib = max(end_steps)
        od = sorted(end_steps)
        od1=sorted(start_steps)

        step = od[1]-od[0]
        step2=-1
        change_step_at = ''
        #         self._change_step_at = str(GRIB.grib_get(self._gribs_for_utils[i],'startStep'))+'-'+str(GRIB.grib_get(self._gribs_for_utils[i],'endStep'))
            #         self._log('Changing time res at %s'%self._change_step_at)
        for i in range(2,len(od)):
            if step2==-1 and od[i]-od[i-1]!=step:
                step2 = od[i]-od[i-1]
                change_step_at = str(od1[i])+'-'+str(od[i])

        return start_grib, end_grib, step, step2, change_step_at

    def getAggregationInfo(self, readerArgs):
        self._gribs_for_utils = self.getGids(**readerArgs)
        if len(self._gribs_for_utils) > 0:
            type_of_step =GRIB.grib_get(self._gribs_for_utils[1],'stepType')  #instant,avg,cumul
            self._mv = GRIB.grib_get_double(self._gribs_for_utils[0],'missingValue')
            start_grib, end_grib,  self._step_grib, self._step_grib2, self._change_step_at = self.getStartEndAndSteps()
            self._log("Grib input step %d [type of step: %s]"%(self._step_grib,type_of_step))
            self._log('Gribs from %d to %d'%(start_grib,end_grib))
            return self._step_grib, self._step_grib2, self._change_step_at, type_of_step, start_grib, end_grib, self._mv
        #no messages found
        else:
            raise ApplicationException.get_programmatic_exc(3000, details="using "+str(readerArgs))

    def getAux(self):
        gid = self._gribs_for_utils[0]
        val = GRIB.grib_get_double_array(gid,'values')
        return gid, val

    def getMissingValue(self):
        if self._mv == -1 and len(self._gribs_for_utils) > 0:
            self._mv = GRIB.grib_get_double(self._gribs_for_utils[0], 'missingValue')
        return self._mv



    