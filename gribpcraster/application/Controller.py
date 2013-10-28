from gribpcraster.application.manipulation.Conversion import Converter
from gribpcraster.application.manipulation.Correction import Corrector
from gribpcraster.application.interpolation.Interpolation import Interpolator
from gribpcraster.application.readers.GRIBReader import GRIBReader
from gribpcraster.application.writers.PCRasterWriter import PCRasterWriter
from gribpcraster.application.manipulation.Manipulator import Manipulator as mnp
import gribpcraster.application.ExecutionContext as ex
import numpy as np
from util.logger.Logger import Logger

def _findGeoFile(grid_id):
    import util.configuration.geopotentials as g
    return g.read(grid_id)

class Controller:

    def __init__(self, executionContext):
        self._ctx = executionContext
        self._logger = Logger('controller', loggingLevel=executionContext.get('logger.level'))
        self._reader = None
        self._reader2 = None
        self._firstMap = True
        self._interpolator = None
        self._mvEfas = None

    def logExecutionContext(self):
        self._log(str(self._ctx), 'INFO')

    def initExecution(self):
        change_step = ''
        manip_2nd_time_res = None
        m = None
        start_step2 = -1

        self._reader = GRIBReader(self._ctx.get('input.file'))
        input_step, input_step2, change_in_step_at, type_of_param, grib_start, grib_end, mvGrib = self._reader.getAggregationInfo(self._ctx.createCommandForAggregationParams())
        self._interpolator = Interpolator(self._ctx)
        self._mvEfas = self._interpolator.getMissingValueEfas()
        self._interpolator.setMissingValueGrib(mvGrib)
        self._pcRasterWriter = PCRasterWriter(self._ctx.get('outMaps.clone'))
        #read grib messages
        start_step = self._ctx.get('parameter.tstart')
        end_step = self._ctx.get('parameter.tend')
        start_step = 0 if start_step is None else start_step

        if end_step is None:
            end_step = grib_end
        if self._ctx.mustDoManipulation():
            m = mnp(self._ctx.get('aggregation.step'), self._ctx.get('aggregation.type'),
                    input_step, type_of_param, start_step,
                    end_step, self._ctx.get('outMaps.unitTime'), mvGrib)
            start_step, end_step = m.getRealStartEndStep()
        commandArgs = self._ctx.createCommandForGribReader(start_step, end_step)
        return change_step, commandArgs, end_step, input_step, input_step2, m, manip_2nd_time_res, mvGrib, start_step2

    def _readMessages(self, commandArgs):
        messages, shortName = self._reader.getSelectedMessages(**commandArgs)
        #values = messages.getValuesOfFirstOrSingleRes()
        type_of_param = messages.getTypeOfStep()
        grid_id = messages.getGridId()
        return grid_id, messages, type_of_param #, values

    def secondResManipulation(self, change_step, end_step, input_step, messages, mvGrib, type_of_param, values):
        #manipulation of second res messages
        start_step2 = int(change_step.start_step) + input_step # start step of the first message at 2nd resolution
        from gribpcraster.application.manipulation.Manipulator import Manipulator as mnp
        m2 = mnp(self._ctx.get('aggregation.step'), self._ctx.get('aggregation.type'),
                 input_step, type_of_param, start_step2,
                 end_step, self._ctx.get('outMaps.unitTime'), mvGrib)
        values2 = m2.doManipulation(messages.getValuesOfSecondRes())
        import collections
        od = collections.OrderedDict(sorted(values2.items(), key=lambda (k, v): (int(k.end_step), v)))
        change_step = od.keys()[0]
        #append to dictionary after manipulation
        values.update(values2)
        od_final = collections.OrderedDict(sorted(values.items(), key=lambda (k, v): (int(k.end_step), v)))
        #overwrite change_step resolution because of manipulation
        values = od_final
        return change_step, values

    def createOutMap(self, grid_id, i, lats, longs, timestep, v):

        self._log("GRIB Values in %s have avg:%.4f, min:%.4f, max:%.4f" % (
        self._ctx.get('parameter.unit'), np.average(v), v.min(), v.max()))
        self._log("Interpolating values for step range/resolution/original timestep: " + str(timestep), 'DEBUG')
        if self._ctx.interpolateWithGrib():
            v = self._interpolator.interpolate_grib(v, -1, grid_id, iMap = i)
        else:
            #interpolating swath data with scipy griddata or with an in house inverse distance code
            v = self._interpolator.interpolate_with_scipy(lats, longs, v, grid_id, iMap = i)
        self._log("Interpolated Values in %s have avg:%.4f, min:%.4f, max:%.4f" % (
        self._ctx.get('parameter.conversionUnit'), np.average(v[v != self._mvEfas]), v[v != self._mvEfas].min(), v[v != self._mvEfas].max()))

        #conversion now is applied at the very beginning of execution, directly:
        #   passing the converter to a Messages method
        # if self._ctx.mustDoConversion():
        #     assert converter is not None
        #     v = converter.convert(v, self._mvEfas)

        if self._ctx.mustDoCorrection():
            corrector = Corrector.getInstance(self._ctx, _findGeoFile(grid_id))
            v = corrector.correct(v)
        self._log("Final Values in %s have avg:%.4f, min:%.4f, max:%.4f" % (self._ctx.get('parameter.conversionUnit'), np.average(v[v != self._mvEfas]), v[v != self._mvEfas].min(), v[v != self._mvEfas].max()))

        mapName = self._nameMap(i)
        self._pcRasterWriter.write(mapName, v, self._mvEfas)

    def read2ndResMessages(self, commandArgs, messages):
        #append messages
        self._reader2 = GRIBReader(self._ctx.get('input.file2'))
        #messages.change_resolution() will return true after this append
        mess_2nd_res, shortName = self._reader2.getSelectedMessages(**commandArgs)
        messages.append_2nd_res_messages(mess_2nd_res)


     ########################################################
    #                   execute method                     #
   ########################################################

    def execute(self):
        converter = None

        change_step, commandArgs, end_step, input_step, input_step2, m, manip_2nd_time_res, mvGrib, start_step2 = self.initExecution()
        grid_id, messages, type_of_param = self._readMessages(commandArgs)

        if self._ctx.isTwoInputFiles():
            #two files as input
            self.read2ndResMessages(commandArgs, messages)

        if self._ctx.mustDoConversion():
                converter = Converter(func=self._ctx.get('parameter.conversionFunction'),
                              cut_off=self._ctx.get('parameter.cutoffnegative'))
                #convert values
                messages.convertValues(converter)

        values = messages.getValuesOfFirstOrSingleRes()

       # values = converter.convert(values, messages.getMissingValue())

        if self._ctx.mustDoManipulation():
            #messages.change_resolution() returns true if two input files with 2 res
            #                                          or single file multires
            if messages.change_resolution():
                change_step = messages.get_change_res_step()
                #end_step1 is the start step of the first message at 2nd resolution
                end_step1 = int(change_step.start_step)
                m.change_end_step(end_step1)
            values = m.doManipulation(values)

        if messages.change_resolution():
            change_step = messages.get_change_res_step()
            lats2=None
            longs2=None
            if not self._ctx.interpolateWithGrib():
                #we need GRIB lats and lons for scipy interpolation
                lats2, longs2=messages.getLatLons2()
            grid_id2 = messages.getGridId2()
            if self._ctx.mustDoManipulation():
                change_step, values = self.secondResManipulation(change_step, end_step, input_step, messages,
                                                                 mvGrib, type_of_param, values)

        #Grib lats/lons are used for interpolation methods griddata, invdist.
        #Not for grib_nearest and grib_invdist
        if not self._ctx.interpolateWithGrib():
            lats, longs = messages.getLatLons()
        else:
            #these "aux" values are used by grib interpolation methods to create tables on disk
            #aux (gid and its values array) are read by GRIBReader which uses the first message selected
            aux_g, aux_v = self._reader.getAux()
            self._interpolator.setAuxToCreateLookup(aux_g, aux_v)
            lats=None
            longs=None

        if self._ctx.mustDoConversion() and converter.mustDoCutOff():
            values = converter.cutOffNegative(values)

        self._log('******** **** WRITING OUT MAPS (Interpolation, correction) **** *************')

        i = 0
        for timestep in values.keys():
            #writing map i
            i += 1
            if messages.change_resolution() and timestep == change_step:
                self._log(">>>>>>>>>>>> Change of resolution at message: "+str(timestep), 'DEBUG')
                #changing interpol parameters to 2nd res
                lats = lats2
                longs = longs2
                grid_id = grid_id2
            v = values[timestep]
            self.createOutMap(grid_id, i, lats, longs, timestep, v)
        
    def close(self):
        self._logger.close()
        if self._reader:
            self._reader.close()
        if self._reader2:
            self._reader2.close()
        self._pcRasterWriter.close()

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def _nameMap(self, iMap):
        # return a filename of the type 8.3  {prefix}[000000].0[0]{seq}
        filename=self._ctx.get('outMaps.namePrefix')
        mapNumber = self._ctx.get('outMaps.fmap')+(iMap-1)*self._ctx.get('outMaps.ext')
        zeroes=11-len(self._ctx.get('outMaps.namePrefix'))-len(str(mapNumber))
        for g in range(zeroes):
            filename += '0'
        filename += str(mapNumber)
        filename=filename[0:8]+'.'+filename[8:11]
        filename = self._ctx.get('outMaps.outDir')+filename
        return filename

    def _getFirstNumber(self):
        return int(self._ctx.get('outMaps.fmap')) if self._ctx.get('outMaps.fmap') else 0