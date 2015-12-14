import gc
import collections

import numpy as np

from main.manipulation.conversion import Converter
from main.manipulation.correction import Corrector
from main.interpolation import Interpolator
from main.readers.grib import GRIBReader
from main.writers.pcraster import PCRasterWriter
from main.manipulation.aggregator import Aggregator
from util.logger import Logger


class Controller:
    def __init__(self, exec_ctx):
        self._ctx = exec_ctx
        self._logger = Logger.get_logger()
        self._reader = None
        # GRIB reader for second spatial resolution file
        self._reader2 = None
        self._firstMap = True
        self._interpolator = None
        self._mv_efas = None
        self._pcraster_writer = None

    def log_execution_context(self):
        self._log(str(self._ctx), 'INFO')

    def init_execution(self):
        m = None

        self._reader = GRIBReader(self._ctx.get('input.file'), w_perturb=self._ctx.has_perturbation_number())
        grib_info = self._reader.get_grib_info(self._ctx.create_select_cmd_for_aggregation_attrs())
        self._interpolator = Interpolator(self._ctx)
        self._mv_efas = self._interpolator.mv_output
        self._interpolator.set_mv_input(grib_info.mv)
        self._pcraster_writer = PCRasterWriter(self._ctx.get('outMaps.clone'))

        # read grib messages
        start_step = self._ctx.get('parameter.tstart', 0)
        end_step = self._ctx.get('parameter.tend', grib_info.end)

        if self._ctx.must_do_correction and self._reader.has_geopotential():
            self._ctx.input_file_has_geopotential()

        if self._ctx.must_do_aggregation:
            m = Aggregator(aggr_step=self._ctx.get('aggregation.step'), aggr_type=self._ctx.get('aggregation.type'),
                           input_step=grib_info.input_step, step_type=grib_info.type_of_param, start_step=start_step,
                           end_step=end_step, unit_time=self._ctx.get('outMaps.unitTime'), mv_grib=grib_info.mv,
                           force_zero_array=self._ctx.get('aggregation.forceZeroArray'))
            start_step, end_step = m.get_real_start_end_steps()
        selector_params = self._ctx.create_select_cmd_for_reader(start_step, end_step)
        return grib_info, selector_params, end_step, m

    def second_res_manipulation(self, start_step, end_step, input_step, messages, mv_grib, type_of_param, values):

        # manipulation of second resolution messages

        m2 = Aggregator(aggr_step=self._ctx.get('aggregation.step'),
                        aggr_type=self._ctx.get('aggregation.type'),
                        input_step=input_step, step_type=type_of_param, start_step=start_step,
                        end_step=end_step, unit_time=self._ctx.get('outMaps.unitTime'), mv_grib=mv_grib,
                        force_zero_array=self._ctx.get('aggregation.forceZeroArray'))
        values2 = m2.do_manipulation(messages.second_resolution_values())
        values.update(values2)
        # overwrite change_step resolution because of manipulation
        change_step = sorted(values2.iterkeys(), key=lambda k: int(k.end_step))[0]
        return change_step, values

    def create_out_map(self, grid_id, i, lats, longs, timestep, v, geodetic_info=None, log_intertable=False, gid=-1,
                       second_spatial_resolution=False):

        # TODO Remove all debug messages. no more useful
        if self._logger.is_debug:
            self._log("\nGRIB Values in %s have avg:%.4f, min:%.4f, max:%.4f" % (
                self._ctx.get('parameter.unit'), np.average(v), v.min(), v.max()))
            self._log('Interpolating values for step range/resolution/original timestep: {}'.format(timestep))

        # FIXME this if else should go into interpolator class
        if self._ctx.interpolate_with_grib:
            v, intertable_was_used = self._interpolator.interpolate_grib(v, gid, grid_id, log_intertable=log_intertable, second_spatial_resolution=second_spatial_resolution)
            if intertable_was_used and second_spatial_resolution:
                # we don't need GRIB messages in memory any longer, at this point
                if self._reader:
                    self._reader.close()
                    self._reader = None
                if self._reader2:
                    self._reader2.close()
                    self._reader2 = None
        else:
            # interpolating gridded data with scipy kdtree
            v = self._interpolator.interpolate_scipy(lats, longs, v, grid_id, geodetic_info, log_intertable=log_intertable)

        if self._logger.is_debug:
            self._log("Interpolated Values in %s have avg:%.4f, min:%.4f, max:%.4f" % (
                self._ctx.get('parameter.conversionUnit'), np.average(v[v != self._mv_efas]), v[v != self._mv_efas].min(),
                v[v != self._mv_efas].max()))

        if self._ctx.must_do_correction:
            corrector = Corrector.get_instance(self._ctx, grid_id)
            v = corrector.correct(v)

        if self._logger.is_debug:
            self._log("Final Values in %s have avg:%.4f, min:%.4f, max:%.4f" % (
                self._ctx.get('parameter.conversionUnit'), np.average(v[v != self._mv_efas]), v[v != self._mv_efas].min(),
                v[v != self._mv_efas].max()))

        self._pcraster_writer.write(self._name_map(i), v, self._mv_efas)

    def read_2nd_res_messages(self, cmd_args, messages):
        # append messages
        self._reader2 = GRIBReader(self._ctx.get('input.file2'), w_perturb=self._ctx.has_perturbation_number())
        # messages.change_resolution() will return true after this append
        mess_2nd_res, short_name = self._reader2.select_messages(**cmd_args)
        messages.append_2nd_res_messages(mess_2nd_res)

    def execute(self):
        converter = None
        lats = None
        longs = None
        geodetic_info = None
        grib_info, grib_select_cmd, end_step, manipulator = self.init_execution()
        mv_grib = grib_info.mv
        input_step = grib_info.input_step

        messages, short_name = self._reader.select_messages(**grib_select_cmd)
        grid_id = messages.grid_id
        type_of_param = messages.type_of_step

        if self._ctx.is_2_input_files():
            # two files as input (-i and -I input arguments were given)
            self.read_2nd_res_messages(grib_select_cmd, messages)
            # inject aux attributes for interpolation into main reader, to use later
            self._reader.set_2nd_aux(self._reader2.get_main_aux())

        # Grib lats/lons are used for interpolation methods nearest, invdist.
        # Not for grib_nearest and grib_invdist
        if not self._ctx.interpolate_with_grib:
            lats, longs = messages.latlons
            geodetic_info = messages.grid_details
        else:
            # these "aux" values are used by grib interpolation methods to create tables on disk
            # aux (gid and its values array) are read by GRIBReader which uses the first message selected
            aux_g, aux_v, aux_g2, aux_v2 = self._reader.get_gids_for_grib_intertable()
            self._interpolator.aux_for_intertable_generation(aux_g, aux_v, aux_g2, aux_v2)

        # Conversion
        if self._ctx.must_do_conversion:
            converter = Converter(func=self._ctx.get('parameter.conversionFunction'),
                                  cut_off=self._ctx.get('parameter.cutoffnegative'))
            messages.apply_conversion(converter)

        values = messages.first_resolution_values()

        # First resolution manipulation
        if self._ctx.must_do_aggregation:
            if messages.have_change_resolution():
                change_res_step = messages.get_change_res_step()
                # First resolution manipulation by setting end step as start step of the first message at 2nd resolution
                manipulator.change_end_step(int(change_res_step.start_step))
            values = manipulator.do_manipulation(values)

        if messages.have_change_resolution():
            change_res_step = messages.get_change_res_step()
            lats2 = None
            longs2 = None
            geodetic_info2 = None
            start_step2 = int(change_res_step.end_step) + int(self._ctx.get('aggregation.step'))
            if not self._ctx.interpolate_with_grib:
                # we need GRIB lats and lons for scipy interpolation
                lats2, longs2 = messages.latlons_2nd
                geodetic_info2 = messages.grid_details.get_2nd_resolution()
            grid_id2 = messages.grid2_id
            if self._ctx.must_do_aggregation and end_step > start_step2:
                # second resolution manipulation
                change_res_step, values = self.second_res_manipulation(start_step2, end_step, input_step, messages,
                                                                       mv_grib, type_of_param, values)

        if self._ctx.must_do_conversion and converter.must_cut_off:
            values = converter.cut_off_negative(values)

        self._log('******** **** WRITING OUT MAPS (Interpolation, correction) **** *************')

        i = 0
        changed_res = False
        second_resolution = False
        # Ordering values happens only here now - 12/04/2015
        values = collections.OrderedDict(sorted(values.iteritems(), key=lambda (k, v_): (int(k.end_step), v_)))
        for timestep in values.keys():
            log_it = False
            # writing map i
            i += 1
            if messages.have_change_resolution() and timestep == change_res_step:
                self._log(">>>>>>>>>>>> Change of resolution at message: {}".format(str(timestep)))
                # Switching to second resolution
                lats = lats2
                longs = longs2
                grid_id = grid_id2
                geodetic_info = geodetic_info2
                changed_res = True
                second_resolution = True
            v = values[timestep]
            values[timestep] = None
            del values[timestep]
            if i == 1 or changed_res:
                # log the interpolation table name only on first map or at the first extended resolution map
                log_it = True
            self.create_out_map(grid_id, i, lats, longs, timestep, v, geodetic_info, log_intertable=log_it, gid=-1, second_spatial_resolution=second_resolution)
            v = None
            del v
            gc.collect()
            changed_res = False

    def close(self):
        if self._reader:
            self._reader.close()
            self._reader = None
        if self._reader2:
            self._reader2.close()
            self._reader2 = None
        if self._pcraster_writer:
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
