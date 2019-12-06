import logging

from pyg2p.main.manipulation.aggregator import Aggregator
from pyg2p.main.readers.grib import GRIBReader
from pyg2p.main.writers import OutputWriter

from pyg2p.main.manipulation.conversion import Converter


class Controller(object):
    def __init__(self, exec_ctx):
        self.ctx = exec_ctx  # Context object, holding all execution parameters
        self._logger = logging.getLogger()
        self._logger.setLevel(exec_ctx['logger.level'])
        self.grib_reader = None
        # GRIB reader for second spatial resolution file
        self.grib_reader2 = None
        self._firstMap = True
        self._writer = None

    def log_execution_context(self):
        self._logger.info(str(self.ctx))

    def init_execution(self):
        aggregator = None
        self.grib_reader = GRIBReader(self.ctx.get('input.file'), w_perturb=self.ctx.has_perturbation_number)
        grib_info = self.grib_reader.get_grib_info(self.ctx.create_select_cmd_for_aggregation_attrs())
        # self._writer = PCRasterWriter(self._ctx.get('outMaps.clone'))
        #
        # self._writer = self._ctx.get_writer()
        self._writer = OutputWriter(self.ctx, grib_info)

        # read grib messages
        start_step = self.ctx.get('parameter.tstart') or 0
        end_step = self.ctx.get('parameter.tend') or grib_info.end

        if self.ctx.must_do_correction and self.grib_reader.has_geopotential():
            self.ctx.input_file_has_geopotential()

        if self.ctx.must_do_aggregation:
            aggregator = Aggregator(aggr_step=self.ctx.get('aggregation.step'),
                                    aggr_type=self.ctx.get('aggregation.type'),
                                    input_step=grib_info.input_step,
                                    step_type=grib_info.type_of_param,
                                    start_step=start_step,
                                    mv_grib=grib_info.mv,
                                    end_step=end_step,
                                    unit_time=self.ctx.get('outMaps.unitTime'),
                                    force_zero_array=self.ctx.get('aggregation.forceZeroArray'))
            start_step, end_step = aggregator.get_real_start_end_steps()
        selector_params = self.ctx.create_select_cmd_for_reader(start_step, end_step)
        return grib_info, selector_params, end_step, aggregator

    def second_res_manipulation(self, start_step, end_step, input_step, messages, mv_grib, type_of_param, values):

        # manipulation of second resolution messages

        m2 = Aggregator(aggr_step=self.ctx.get('aggregation.step'),
                        aggr_type=self.ctx.get('aggregation.type'),
                        input_step=input_step, step_type=type_of_param, start_step=start_step,
                        end_step=end_step, unit_time=self.ctx.get('outMaps.unitTime'), mv_grib=mv_grib,
                        force_zero_array=self.ctx.get('aggregation.forceZeroArray'))
        values2 = m2.do_manipulation(messages.second_resolution_values())
        values.update(values2)
        # overwrite change_step resolution because of manipulation
        change_step = sorted(values2.keys(), key=lambda k: int(k.end_step))[0]
        return change_step, values

    def read_2nd_res_messages(self, cmd_args, messages):
        # append messages
        self.grib_reader2 = GRIBReader(self.ctx.get('input.file2'), w_perturb=self.ctx.has_perturbation_number)
        # messages.change_resolution() will return true after this append
        mess_2nd_res, short_name = self.grib_reader2.select_messages(**cmd_args)
        messages.append_2nd_res_messages(mess_2nd_res)

    def execute(self):
        converter = None
        grib_info, grib_select_cmd, end_step, manipulator = self.init_execution()
        mv_grib = grib_info.mv
        input_step = grib_info.input_step

        messages, short_name = self.grib_reader.select_messages(**grib_select_cmd)
        type_of_param = messages.type_of_step

        if self.ctx.is_2_input_files():
            # two files as input (-i and -I input arguments were given)
            self.read_2nd_res_messages(grib_select_cmd, messages)
            # inject aux attributes for interpolation into main reader, to use later
            self.grib_reader.set_2nd_aux(self.grib_reader2.get_main_aux())

        # Grib lats/lons are used for interpolation methods nearest, invdist.
        # Not for grib_nearest and grib_invdist
        aux_g, aux_v, aux_g2, aux_v2 = self.grib_reader.get_gids_for_grib_intertable()
        if self.ctx.interpolate_with_grib:
            # these "aux" values are used by grib interpolation methods to create tables on disk
            # aux (gid and its values array) are read by GRIBReader which uses the first message selected
            self._writer.aux_for_intertable_generation(aux_g, aux_v, aux_g2, aux_v2)

        # Conversion
        if self.ctx.must_do_conversion:
            converter = Converter(func=self.ctx.get('parameter.conversionFunction'),
                                  cut_off=self.ctx.get('parameter.cutoffnegative'))
            messages.apply_conversion(converter)

        values = messages.first_resolution_values()

        # First resolution manipulation
        if self.ctx.must_do_aggregation:
            if messages.have_resolution_change():
                change_res_step = messages.change_resolution_step()
                # First resolution manipulation by setting end step as start step of the first message at 2nd resolution
                manipulator.change_end_step(int(change_res_step.start_step))
            values = manipulator.do_manipulation(values)

        change_res_step = None
        if messages.have_resolution_change():
            change_res_step = messages.change_resolution_step()
            start_step2 = int(change_res_step.end_step) + int(self.ctx.get('aggregation.step'))
            # we need GRIB lats and lons only for scipy interpolation
            if self.ctx.must_do_aggregation and end_step > start_step2:
                # second resolution manipulation
                change_res_step, values = self.second_res_manipulation(start_step2, end_step, input_step, messages,
                                                                       mv_grib, type_of_param, values)

        if converter and converter.must_cut_off:
            values = converter.cut_off_negative(values)
        self._logger.debug('******** **** WRITING OUT MAPS (Interpolation, correction) **** *************')
        self._writer.write_maps(values, messages, change_res_step=change_res_step)

    def close(self):
        if self.grib_reader:
            self.grib_reader.close()
            self.grib_reader = None
        if self.grib_reader2:
            self.grib_reader2.close()
            self.grib_reader2 = None
        if self._writer:
            self._writer.close()

    def _log(self, message, level='DEBUG'):
        self._logger.log(logging._checkLevel(level), message)
