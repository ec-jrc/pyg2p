from gribpcraster.application.manipulation.Conversion import Converter
from gribpcraster.application.manipulation.Correction import Corrector
from gribpcraster.application.interpolation.Interpolation import Interpolator
from gribpcraster.application.readers.GRIBReader import GRIBReader
from gribpcraster.application.writers.PCRasterWriter import PCRasterWriter
from gribpcraster.application.manipulation.Manipulator import Manipulator as mnp
import gribpcraster.application.ExecutionContext as ex
import numpy as np
from util.logger.Logger import Logger
import gc


def _findGeoFile(grid_id):
    import util.configuration.geopotentials as g

    return g.read(grid_id)


class Controller:
    def __init__(self, executionContext):
        self._ctx = executionContext
        self._logger = Logger('controller', loggingLevel=executionContext.get('logger.level'))
        self._reader = None
        #GRIB reader for second spatial resolution file
        self._reader2 = None
        self._firstMap = True
        self._interpolator = None
        self._mvEfas = None
        self._pcraster_writer = None

    def log_execution_context(self):
        self._log(str(self._ctx), 'INFO')

    def init_execution(self):
        change_step = ''
        manip_2nd_time_res = None
        m = None
        start_step2 = -1

        self._reader = GRIBReader(self._ctx.get('input.file'),
                                  w_perturb=self._ctx.has_perturbation_number())
        input_step, input_step2, change_in_step_at, type_of_param, grib_start, grib_end, mvGrib = self._reader.getAggregationInfo(
            self._ctx.create_select_cmd_for_aggregation_attrs())
        self._interpolator = Interpolator(self._ctx)
        self._mvEfas = self._interpolator.getMissingValueEfas()
        self._interpolator.setMissingValueGrib(mvGrib)
        self._pcraster_writer = PCRasterWriter(self._ctx.get('outMaps.clone'))
        #read grib messages
        start_step = 0 if self._ctx.get('parameter.tstart') is None else self._ctx.get('parameter.tstart')
        end_step = grib_end if self._ctx.get('parameter.tend') is None else self._ctx.get('parameter.tend')

        if self._ctx.must_do_manipulation():
            m = mnp(self._ctx.get('aggregation.step'), self._ctx.get('aggregation.type'),
                    input_step, type_of_param, start_step,
                    end_step, self._ctx.get('outMaps.unitTime'), mvGrib,
                    force_zero_array=self._ctx.get('aggregation.forceZeroArray'))
            start_step, end_step = m.get_real_start_end_steps()
        selector_params = self._ctx.create_select_cmd_for_reader(start_step, end_step)
        return change_step, selector_params, end_step, input_step, input_step2, m, manip_2nd_time_res, mvGrib, start_step2

    def _read_messages(self, selector_params):

        messages, shortName = self._reader.getSelectedMessages(**selector_params)
        type_of_param = messages.getTypeOfStep()
        grid_id = messages.getGridId()
        return grid_id, messages, type_of_param

    def secondResManipulation(self, change_step, end_step, input_step, messages, mvGrib, type_of_param, values):

        #manipulation of second res messages
        start_step2 = int(change_step.end_step) + int(self._ctx.get('aggregation.step'))
        m2 = mnp(self._ctx.get('aggregation.step'), self._ctx.get('aggregation.type'),
                 input_step, type_of_param, start_step2,
                 end_step, self._ctx.get('outMaps.unitTime'), mvGrib,
                 force_zero_array=self._ctx.get('aggregation.forceZeroArray'))
        values2 = m2.do_manipulation(messages.getValuesOfSecondRes())
        values.update(values2)
        import collections
        #overwrite change_step resolution because of manipulation
        od = collections.OrderedDict(sorted(values2.iteritems(), key=lambda (k, v): (int(k.end_step), v)))
        change_step = od.keys()[0]
        del od
        values = collections.OrderedDict(sorted(values.iteritems(), key=lambda (k, v): (int(k.end_step), v)))
        gc.collect()
        return change_step, values

    def createOutMap(self, grid_id, i, lats, longs, timestep, v, log_intertable=False, gid=-1,
                     second_spatial_resolution=False):

        if self._ctx.get('logging.level') == 'DEBUG':
            self._log("GRIB Values in %s have avg:%.4f, min:%.4f, max:%.4f" % (
                self._ctx.get('parameter.unit'), np.average(v), v.min(), v.max()), 'DEBUG')
            self._log("Interpolating values for step range/resolution/original timestep: " + str(timestep), 'DEBUG')
        if self._ctx.interpolate_with_grib():
            v, intertable_was_used = self._interpolator.interpolate_grib(v, gid, grid_id, log_intertable=log_intertable,
                                                                         second_spatial_resolution=second_spatial_resolution)
            if (self._reader is not None or self._reader2 is not None) and intertable_was_used:
                # we don't need GRIB messages in memory any longer, at this point
                if self._reader is not None and not second_spatial_resolution:
                    self._reader.close()
                    self._reader = None
                elif self._reader2 is not None and second_spatial_resolution:
                    self._reader2.close()
                    self._reader2 = None
        else:
            #interpolating swath data with scipy griddata or with an in house inverse distance code
            v = self._interpolator.interpolate_with_scipy(lats, longs, v, grid_id, log_intertable=log_intertable)

        if self._ctx.get('logging.level') == 'DEBUG':
            self._log("Interpolated Values in %s have avg:%.4f, min:%.4f, max:%.4f" % (
                self._ctx.get('parameter.conversionUnit'), np.average(v[v != self._mvEfas]), v[v != self._mvEfas].min(),
                v[v != self._mvEfas].max()))

        if self._ctx.must_do_correction():
            corrector = Corrector.getInstance(self._ctx, _findGeoFile(grid_id))
            v = corrector.correct(v)
        if self._ctx.get('logging.level') == 'DEBUG':
            self._log("Final Values in %s have avg:%.4f, min:%.4f, max:%.4f" % (
                self._ctx.get('parameter.conversionUnit'), np.average(v[v != self._mvEfas]), v[v != self._mvEfas].min(),
                v[v != self._mvEfas].max()))

        self._pcraster_writer.write(self._name_map(i), v, self._mvEfas)


    def read_2nd_res_messages(self, commandArgs, messages):
        #append messages
        self._reader2 = GRIBReader(self._ctx.get('input.file2'), w_perturb=self._ctx.has_perturbation_number())
        #messages.change_resolution() will return true after this append
        mess_2nd_res, shortName = self._reader2.getSelectedMessages(**commandArgs)
        messages.append_2nd_res_messages(mess_2nd_res)

        ########################################################
        #                   execute method                     #
        ########################################################

    def execute(self):
        converter = None

        change_res_step, commandArgs, end_step, input_step, input_step2, manipulator, manip_2nd_time_res, mvGrib, start_step2 = self.init_execution()
        grid_id, messages, type_of_param = self._read_messages(commandArgs)

        #Grib lats/lons are used for interpolation methods griddata, invdist.
        #Not for grib_nearest and grib_invdist
        if not self._ctx.interpolate_with_grib():
            lats, longs = messages.getLatLons()
        else:
            #these "aux" values are used by grib interpolation methods to create tables on disk
            #aux (gid and its values array) are read by GRIBReader which uses the first message selected
            aux_g, aux_v, aux_g2, aux_v2 = self._reader.get_gids_for_grib_intertable()
            self._interpolator.setAuxToCreateLookup(aux_g, aux_v, aux_g2, aux_v2)
            lats = None
            longs = None

        if self._ctx.is_2_input_files():
            #two files as input
            self.read_2nd_res_messages(commandArgs, messages)
            #inject aux attributes for interpolation into main reader, to use later
            self._reader.set_2nd_aux(self._reader2.get_main_aux())

        if self._ctx.must_do_conversion():
            converter = Converter(func=self._ctx.get('parameter.conversionFunction'),
                                  cut_off=self._ctx.get('parameter.cutoffnegative'))
            messages.convertValues(converter)

        values = messages.getValuesOfFirstOrSingleRes()
        if self._ctx.must_do_manipulation():
            if messages.have_change_resolution():
                change_res_step = messages.get_change_res_step()  # Key object
                #start step of the first message at 2nd resolution
                manipulator.change_end_step(int(change_res_step.start_step))
            values = manipulator.do_manipulation(values)

        if messages.have_change_resolution():
            change_res_step = messages.get_change_res_step()
            lats2 = None
            longs2 = None
            if not self._ctx.interpolate_with_grib():
                #we need GRIB lats and lons for scipy interpolation
                lats2, longs2 = messages.getLatLons2()
            grid_id2 = messages.getGridId2()
            if self._ctx.must_do_manipulation():
                change_res_step, values = self.secondResManipulation(change_res_step, end_step, input_step, messages,
                                                                     mvGrib, type_of_param, values)

        if self._ctx.must_do_conversion() and converter.mustDoCutOff():
            values = converter.cutOffNegative(values)

        self._log('******** **** WRITING OUT MAPS (Interpolation, correction) **** *************')

        i = 0
        changed_res = False
        second_resolution = False

        for timestep in values.keys():
            log_it = False
            #writing map i
            i += 1
            if messages.have_change_resolution() and timestep == change_res_step:
                self._log(">>>>>>>>>>>> Change of resolution at message: " + str(timestep), 'DEBUG')
                #changing interpol parameters to 2nd res
                lats = lats2
                longs = longs2
                grid_id = grid_id2
                changed_res = True
                second_resolution = True
            v = values[timestep]
            values[timestep] = None
            del values[timestep]
            if i == 1 or changed_res:
                #log the interpolation table name only on first map or at the first extended resolution map
                log_it = True
            self.createOutMap(grid_id, i, lats, longs, timestep, v, log_intertable=log_it, gid=-1,
                              second_spatial_resolution=second_resolution)
            v = None
            del v
            gc.collect()
            changed_res = False

    def close(self):
        self._logger.close()
        if self._reader:
            self._reader.close()
            self._reader = None
        if self._reader2:
            self._reader2.close()
            self._reader2 = None
        self._pcraster_writer.close()

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def _name_map(self, i_map):
        # return a filename of the type 8.3  {prefix}[000000].0[0]{seq}
        filename = self._ctx.get('outMaps.namePrefix')
        map_number = self._ctx.get('outMaps.fmap') + (i_map - 1) * self._ctx.get('outMaps.ext')
        zeroes = 11 - len(self._ctx.get('outMaps.namePrefix')) - len(str(map_number))
        for g in range(zeroes):
            filename += '0'
        filename += str(map_number)
        filename = filename[0:8] + '.' + filename[8:11]
        filename = self._ctx.get('outMaps.outDir') + filename
        return filename

    # def _getFirstNumber(self):
    #     return int(self._ctx.get('outMaps.fmap')) if self._ctx.get('outMaps.fmap') else 0