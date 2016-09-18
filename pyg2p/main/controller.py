from pyg2p.main.manipulation.aggregator import Aggregator
from pyg2p.main.readers.grib import GRIBReader
from pyg2p.main.writers import OutputWriter

from pyg2p.main.manipulation.conversion import Converter
from pyg2p.util.logger import Logger


class Controller(object):
    def __init__(self, exec_ctx):
        self._ctx = exec_ctx
        self._logger = Logger.get_logger()
        self._reader = None
        # GRIB reader for second spatial resolution file
        self._reader2 = None
        self._firstMap = True
        self._writer = None

    def log_execution_context(self):
        self._log(str(self._ctx), 'INFO')

    def init_execution(self):
        aggregator = None
        self._reader = GRIBReader(self._ctx.get('input.file'), w_perturb=self._ctx.has_perturbation_number)
        grib_info = self._reader.get_grib_info(self._ctx.create_select_cmd_for_aggregation_attrs())
        # self._writer = PCRasterWriter(self._ctx.get('outMaps.clone'))
        #
        # self._writer = self._ctx.get_writer()
        self._writer = OutputWriter(self._ctx, grib_info)

        # read grib messages
        start_step = self._ctx.get('parameter.tstart') or 0
        end_step = self._ctx.get('parameter.tend') or grib_info.end

        if self._ctx.must_do_correction and self._reader.has_geopotential():
            self._ctx.input_file_has_geopotential()

        if self._ctx.must_do_aggregation:
            aggregator = Aggregator(aggr_step=self._ctx.get('aggregation.step'),
                                    aggr_type=self._ctx.get('aggregation.type'),
                                    input_step=grib_info.input_step,
                                    step_type=grib_info.type_of_param,
                                    start_step=start_step,
                                    mv_grib=grib_info.mv,
                                    end_step=end_step,
                                    unit_time=self._ctx.get('outMaps.unitTime'),
                                    force_zero_array=self._ctx.get('aggregation.forceZeroArray'))
            start_step, end_step = aggregator.get_real_start_end_steps()
        selector_params = self._ctx.create_select_cmd_for_reader(start_step, end_step)
        return grib_info, selector_params, end_step, aggregator

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

    def read_2nd_res_messages(self, cmd_args, messages):
        # append messages
        self._reader2 = GRIBReader(self._ctx.get('input.file2'), w_perturb=self._ctx.has_perturbation_number)
        # messages.change_resolution() will return true after this append
        mess_2nd_res, short_name = self._reader2.select_messages(**cmd_args)
        messages.append_2nd_res_messages(mess_2nd_res)

    def execute(self):
        converter = None
        grib_info, grib_select_cmd, end_step, manipulator = self.init_execution()
        mv_grib = grib_info.mv
        input_step = grib_info.input_step

        messages, short_name = self._reader.select_messages(**grib_select_cmd)
        type_of_param = messages.type_of_step

        if self._ctx.is_2_input_files():
            # two files as input (-i and -I input arguments were given)
            self.read_2nd_res_messages(grib_select_cmd, messages)
            # inject aux attributes for interpolation into main reader, to use later
            self._reader.set_2nd_aux(self._reader2.get_main_aux())

        # Grib lats/lons are used for interpolation methods nearest, invdist.
        # Not for grib_nearest and grib_invdist
        aux_g, aux_v, aux_g2, aux_v2 = self._reader.get_gids_for_grib_intertable()
        if self._ctx.interpolate_with_grib:
            # these "aux" values are used by grib interpolation methods to create tables on disk
            # aux (gid and its values array) are read by GRIBReader which uses the first message selected
            self._writer.aux_for_intertable_generation(aux_g, aux_v, aux_g2, aux_v2)

        # Conversion
        if self._ctx.must_do_conversion:
            converter = Converter(func=self._ctx.get('parameter.conversionFunction'),
                                  cut_off=self._ctx.get('parameter.cutoffnegative'))
            messages.apply_conversion(converter)

        values = messages.first_resolution_values()

        # First resolution manipulation
        if self._ctx.must_do_aggregation:
            if messages.have_resolution_change():
                change_res_step = messages.change_resolution_step()
                # First resolution manipulation by setting end step as start step of the first message at 2nd resolution
                manipulator.change_end_step(int(change_res_step.start_step))
            values = manipulator.do_manipulation(values)

        change_res_step = None
        if messages.have_resolution_change():
            change_res_step = messages.change_resolution_step()
            start_step2 = int(change_res_step.end_step) + int(self._ctx.get('aggregation.step'))
            # we need GRIB lats and lons only for scipy interpolation
            if self._ctx.must_do_aggregation and end_step > start_step2:
                # second resolution manipulation
                change_res_step, values = self.second_res_manipulation(start_step2, end_step, input_step, messages,
                                                                       mv_grib, type_of_param, values)

        if self._ctx.must_do_conversion and converter.must_cut_off:
            values = converter.cut_off_negative(values)

        self._log('******** **** WRITING OUT MAPS (Interpolation, correction) **** *************')
        self._writer.write_maps(values, messages, change_res_step=change_res_step)

    def close(self):
        if self._reader:
            self._reader.close()
            self._reader = None
        if self._reader2:
            self._reader2.close()
            self._reader2 = None
        if self._writer:
            self._writer.close()

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def _name_map(self, i_map):
        # return a full path for output map, of the type 8.3  {prefix}[000000].0[0]{seq}
        filename = self._ctx.get('outMaps.namePrefix')
        map_number = self._ctx.get('outMaps.fmap') + (i_map - 1) * self._ctx.get('outMaps.ext')
        zeroes = 11 - len(self._ctx.get('outMaps.namePrefix')) - len(str(map_number))
        for g in range(zeroes):
            filename += '0'
        filename += str(map_number)
        filename = filename[0:8] + '.' + filename[8:11]
        filename = self._ctx.get('outMaps.outDir') + filename
        return filename
