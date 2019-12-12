import os
import datetime
import abc
import collections

import numpy as np

from pyg2p import Loggable
from pyg2p.main.interpolation import Interpolator
from pyg2p.main.manipulation.correction import Corrector


class Writer(Loggable, metaclass=abc.ABCMeta):
    FORMAT = None

    def __init__(self, *args):
        super().__init__()
        self._clone_map = args[0]
        self._log('Set clone for writing {} maps: {}'.format(self.FORMAT, self._clone_map))

    @abc.abstractmethod
    def write(self, *args, **kwargs):
        raise NotImplementedError()


class OutputWriter(Loggable):
    """
    This class performs interpolation and write resulting values to PCRaster/netCDF files.
    """
    def __init__(self, ctx, grib_info):
        super().__init__()
        self.ctx = ctx
        self.interpolator = Interpolator(ctx, mv_input=grib_info.mv)
        self.writer = self.get_writer()  # instance of PCRasterWriter or NetCDFWriter
        self._logger.setLevel(ctx['logger.level'])

    def aux_for_intertable_generation(self, aux_g, aux_v, aux_g2, aux_v2):
        self.interpolator.aux_for_intertable_generation(aux_g, aux_v, aux_g2, aux_v2)

    def _write_maps_netcdf(self, values, messages, change_res_step):
        """
        Prepare values for netCDF file writing (time and values)
        Note that lats and lons values are prepared from netcdf writer init_dataset method
        They come from latitude/longitude pcraster maps values
        """
        is_second_res = False
        lats, longs = messages.latlons
        geodetic_info = messages.grid_details
        grid_id = messages.grid_id
        time_values = []
        out_values = []
        for i, (timestep, v) in enumerate(values.items()):
            # note: timestep and change_res_step are instances of domain.step.Step class
            # writing map i
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
            out_v[out_v == self.interpolator.mv_output] = np.nan
            out_values.append(out_v)
            time_values.append(timestep.end_step)
        # prepare values for netcdf writing
        time_values = np.array(time_values, dtype=np.int32)
        out_values = np.array(out_values, dtype=np.float64)
        out_filename = self._name_netcdf_file()
        var_args = dict(prefix=self.ctx.get('outMaps.namePrefix'),
                        unit=self.ctx.get('parameter.conversionUnit'),
                        var_long_name=self.ctx.get('parameter.description'),
                        data_date=messages.data_date)
        self.writer.init_dataset(out_filename)

        self.writer.write(out_values, time_values, **var_args)

    def _write_maps_pcraster(self, values, messages, change_res_step):
        is_second_res = False
        lats, longs = messages.latlons
        geodetic_info = messages.grid_details
        grid_id = messages.grid_id

        for i, (timestep, v) in enumerate(values.items()):
            # note: timestep and change_res_step are instances of domain.step.Step class
            # writing map i
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
            self.writer.write(self._name_pcr_map(i + 1), out_v)

    def write_maps(self, values, messages, change_res_step=None):
        write_method = getattr(self, '_write_maps_{}'.format(self.ctx.get('outMaps.format')))
        # Ordering values happens only here now - 12/04/2015
        values = collections.OrderedDict(sorted(values.items(), key=lambda k: int(k[0].end_step)))
        write_method(values, messages, change_res_step)

    def _name_netcdf_file(self):
        fn_format = '{varname}_{date}_{aggregation}.nc'.format
        fmt = '%Y-%m-%d'
        # noinspection PyTypeChecker
        date_str = datetime.datetime.strftime(datetime.datetime.now(), fmt)
        filename = fn_format(varname=self.ctx.get('outMaps.namePrefix'),
                             date=date_str,
                             aggregation=self.ctx.get('aggregation.type'))
        out_filename = os.path.join(self.ctx.get('outMaps.outDir'), filename)
        return out_filename

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

    def close(self):
        self.writer.close()

    def get_writer(self):
        """
        Inspect outMaps.format and return the right Writer class
        return: instance of Writer (PCRasterWriter or NetCDFWriter)
        """
        out_format = self.ctx.get('outMaps.format')
        map_clone = self.ctx.get('outMaps.clone')
        lat_map = self.ctx.get('interpolation.latMap')
        lon_map = self.ctx.get('interpolation.lonMap')
        if out_format == 'pcraster':
            from pyg2p.main.writers.pcr import PCRasterWriter
            return PCRasterWriter(map_clone)
        # netcdf
        from pyg2p.main.writers.netcdf import NetCDFWriter
        return NetCDFWriter(map_clone, lat_map, lon_map)
