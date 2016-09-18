import abc

import collections
import os

from pyg2p.util.logger import Logger
from pyg2p.main.interpolation import Interpolator
from pyg2p.main.manipulation.correction import Corrector


class Writer(object):
    __metaclass__ = abc.ABCMeta
    FORMAT = None

    @abc.abstractmethod
    def write(self, output_map_name, values):
        raise NotImplementedError()


class OutputWriter(object):
    def __init__(self, ctx, grib_info):
        self.ctx = ctx
        self.interpolator = Interpolator(ctx, mv_input=grib_info.mv)
        self.writer = ctx.get_writer()  # instance of PCRasterWriter or NetCDFWriter
        self.logger = Logger.get_logger()

    def aux_for_intertable_generation(self, aux_g, aux_v, aux_g2, aux_v2):
        self.interpolator.aux_for_intertable_generation(aux_g, aux_v, aux_g2, aux_v2)

    def _write_maps_netcdf(self, values, messages, change_res_step):
        filename = self.ctx.get('outMaps.namePrefix') + '.nc'
        out_filename = os.path.join(self.ctx.get('outMaps.outDir'), filename)
        self.writer.init_dataset(out_filename)
        self.writer.write(out_filename, values, messages, change_res_step)

    def _write_maps_pcraster(self, values, messages, change_res_step):
        i = 0
        is_second_res = False
        lats, longs = messages.latlons
        geodetic_info = messages.grid_details
        grid_id = messages.grid_id

        for timestep, v in values.iteritems():
            # writing map i
            i += 1
            if messages.have_resolution_change() and timestep == change_res_step:
                # Switching to second resolution
                lats, longs = messages.latlons_2nd
                geodetic_info = messages.grid_details.get_2nd_resolution()
                grid_id = messages.grid2_id
                is_second_res = True
            out_v = self.interpolator.interpolate(lats, longs, v, grid_id, geodetic_info, is_second_res=is_second_res)
            if self.ctx.must_do_correction:
                corrector = Corrector.get_instance(self.ctx, grid_id)
                out_v = corrector.correct(out_v)
            self.writer.write(self._name_pcr_map(i), out_v)

    def write_maps(self, values, messages, change_res_step=None):
        write_method = getattr(self, '_write_maps_{}'.format(self.ctx.get('outMaps.format')))
        # Ordering values happens only here now - 12/04/2015
        values = collections.OrderedDict(sorted(values.iteritems(), key=lambda (k, _): int(k.end_step)))
        write_method(values, messages, change_res_step)

    def _name_pcr_map(self, i_map):
        # Used for pcraster output maps
        # return a full path for output map, of the type 8.3  {prefix}[000000].0[0]{seq}
        filename = self.ctx.get('outMaps.namePrefix')
        map_number = self.ctx.get('outMaps.fmap') + (i_map - 1) * self.ctx.get('outMaps.ext')
        zeroes = 11 - len(self.ctx.get('outMaps.namePrefix')) - len(str(map_number))
        for g in range(zeroes):
            filename += '0'
        filename += str(map_number)
        filename = filename[0:8] + '.' + filename[8:11]
        filename = os.path.join(self.ctx.get('outMaps.outDir'), filename)
        return filename

    def _log(self, message, level='DEBUG'):
        self.logger.log(message, level)

    def close(self):
        self.writer.close()
