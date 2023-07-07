import collections
from functools import partial
from pathlib import Path
from types import MethodType

import numpy.ma as ma

from . import Controller, Configuration
from .context import Context
from .interpolation import Interpolator
from .manipulation.aggregator import ACCUMULATION
from .manipulation.correction import Corrector
from .readers import GRIBReader, PCRasterReader
from ..main import pyg2p_exe
from ..util import strings
from ..util.strings import to_argv, to_argdict


def command(*args, **kwargs):
    return Command(*args, **kwargs)


def run_command(cmd):
    argv = to_argv(str(cmd))
    return pyg2p_exe(argv[1:])


def _a(opt, self, param=''):
    self._d[opt] = param
    return self


class Command:
    """
    Class to encapsulate a pyg2p.py command. It uses builder pattern to construct the command.
    Look at the cmds_map dict for available methods to add an argument to command.
    Usage:
    c = Command()
    c = c.with_cmdpath('average.json').with_inputfile('rain.grb').with_outdir('./')
    c = c.with_create_intertable().with_parallel().with_out_format('netcdf')  # boolean args are created without args
    """
    cmds_map = {'cmdpath': '-c', 'inputfile': '-i', 'second_input_file': '-I',
                'eps': '-m', 'tend': '-e', 'tstart': '-s', 'datatime': '-T', 'datadate': '-D',
                'ext': '-x', 'fmap': '-f', 'outdir': '-o', 'nameprefix': '-n', 
                'scaleFactor': '-S', 'offset': '-O', 
                'validMax': '-vM', 'validMin': '-vm', 'valueFormat': '-vf',
                'log_level': '-l', 'log_dir': '-d', 'out_format': '-F', 'outputStepUnits': '-U',
                'create_intertable': '-B', 'parallel': '-X', 'intertable_dir': '-N'}

    def _a(self, opt, param=''):
        self._d[opt] = param
        return self

    def __init__(self, cmd_string=None, **params):
        cmd_string = cmd_string.lstrip('pyg2p').strip()
        if params:
            opts = params.copy()
            # string interpolation
            for var in opts:
                opts[var] = opts[var].as_posix() if isinstance(opts[var], Path) else str(opts[var])  # as string
                cmd_string = cmd_string.replace('{%s}' % var, opts[var])
        # adding flag underApi
        self._d = {} if not cmd_string else to_argdict(f'{cmd_string} -A')
        # adding log level
        if '-l' not in self._d.keys():
            self._a('-l', 'ERROR')
        # generate API
        for method_suffix, opt in self.cmds_map.items():
            setattr(self, f'with_{method_suffix}', MethodType(partial(_a, opt), self))

    def __str__(self):
        cmd = 'pyg2p '
        self._d = collections.OrderedDict(sorted(self._d.items(), key=lambda k: k[0]))
        args = ''.join(['%s %s ' % (key, value) for (key, value) in self._d.items()]).strip()
        return cmd + args

    def run(self):
        argv = to_argv(str(self))
        return pyg2p_exe(argv[1:])


class ApiContext(Context):
    """

    """
    def __init__(self, params_dict):
        """
        :param params_dict: dict

        """
        super().__init__()
        self.api_conf = params_dict
        self._define_exec_params()

        # check numbers, existing dirs and files, supported options, semantics etc.
        self._check_exec_params()

    def _define_exec_params(self):
        self._vars['logger.level'] = self.api_conf.get('loggerLevel', 'INFO')

        self._vars['input.file'] = self.api_conf['inputFile']
        self._vars['parameter.tstart'] = self.api_conf['start']
        self._vars['parameter.tend'] = self.api_conf['end']
        self._vars['parameter.dataTime'] = self.api_conf.get('dataTime')
        self._vars['parameter.dataDate'] = self.api_conf.get('dataDate')
        self._vars['interpolation.dir'] = self.api_conf.get('intertableDir')
        self._vars['geopotential.dir'] = self.api_conf.get('geopotentialDir')
        self._vars['interpolation.create'] = self.api_conf.get('createIntertable', False)
        self._vars['interpolation.parallel'] = self.api_conf.get('interpolationParallel', True)
        self._vars['outMaps.fmap'] = self.api_conf.get('fmap')
        self._vars['outMaps.ext'] = self.api_conf.get('ext')
        self._vars['outMaps.namePrefix'] = self.api_conf.get('namePrefix')
        self._vars['outMaps.scaleFactor'] = self.api_conf.get('scaleFactor')
        self._vars['outMaps.offset'] = self.api_conf.get('offset')
        self._vars['outMaps.validMin'] = self.api_conf.get('validMin')
        self._vars['outMaps.validMax'] = self.api_conf.get('validMax')
        self._vars['outMaps.valueFormat'] = self.api_conf.get('valueFormat')
        self._vars['outMaps.outputStepUnits'] = self.api_conf.get('outputStepUnits')
        self._vars['outMaps.offset'] = self.api_conf.get('offset')
        self._vars['outMaps.outDir'] = './'  # not used
        self._vars['parameter.perturbationNumber'] = self.api_conf.get('perturbationNumber')
        self._vars['input.file2'] = self.api_conf.get('inputFile2')
        self._vars['input.two_resolution'] = bool(self._vars['input.file2'])
        self._vars['geopotential'] = self.api_conf.get('addGeopotential')
        self._to_add_geopotential = bool(self._vars['geopotential'])
        self._vars['download_configuration'] = self.api_conf.get('downloadConf')
        self._vars['under_api'] = True
        self._vars['check_conf'] = self.api_conf.get('checkConf')

        # INTERTABLES and GEOPOTENTIALS paths handling
        user_intertables = self._vars['interpolation.dir'] or self.configuration.default_interpol_dir
        user_geopotentials = self._vars['geopotential.dir'] or self.configuration.default_geopotential_dir
        if not self.configuration.intertables.data_path:
            self.configuration.intertables.data_path = user_intertables
        self._vars['interpolation.dirs'] = {'global': self.configuration.intertables.global_data_path,
                                            'user': user_intertables}
        self._vars['geopotential.dirs'] = {'global': self.configuration.geopotentials.global_data_path,
                                           'user': user_geopotentials}

        self.is_config_command = self.to_add_geopotential or self.to_download_conf or self.to_check_conf
        self._vars['execution.doAggregation'] = False
        self._vars['execution.doConversion'] = False
        self._vars['execution.doCorrection'] = False
        self._vars['parameter.conversionId'] = None

        self._vars['parameter.shortName'] = self.api_conf['Parameter']['shortName']
        parameter = self.configuration.parameters.get(self._vars['parameter.shortName'])
        self._vars['parameter.description'] = parameter['@description']
        self._vars['parameter.unit'] = parameter['@unit']
        self._vars['parameter.conversionUnit'] = parameter['@unit']

        if self.api_conf['Parameter'].get('applyConversion'):
            self._vars['execution.doConversion'] = True
            self._vars['parameter.conversionId'] = self.api_conf['Parameter']['applyConversion']
            conversion = self.configuration.parameters.get_conversion(parameter, self._vars['parameter.conversionId'])
            self._vars['parameter.conversionUnit'] = conversion['@unit']
            self._vars['parameter.conversionFunction'] = conversion['@function']
            self._vars['parameter.cutoffnegative'] = strings.to_boolean(conversion.get('@cutOffNegative'))

        if self.api_conf['Parameter'].get('correctionFormula') and self.api_conf['Parameter'].get('gem') and self.api_conf['Parameter'].get('demMap'):
            self._vars['execution.doCorrection'] = True
            self._vars['correction.formula'] = self.api_conf['Parameter']['correctionFormula']
            self._vars['correction.gemFormula'] = self.api_conf['Parameter']['gem']
            self._vars['correction.demMap'] = self.api_conf['Parameter']['demMap']
            if not self._vars['geopotential.dir'] and self.api_conf.get('geopotentialDir'):
                self._vars['geopotential.dirs']['user'] = self.api_conf['geopotentialDir']

        self._vars['outMaps.clone'] = self.api_conf['OutMaps']['cloneMap']
        interpolation_conf = self.api_conf['OutMaps']['Interpolation']
        self._vars['interpolation.mode'] = interpolation_conf.get('mode', self.default_values['interpolation.mode'])
        self._vars['interpolation.use_broadcasting'] = interpolation_conf.get('use_broadcasting', False)
        self._vars['interpolation.rotated_target'] = interpolation_conf.get('rotated_target', False)
        if not self._vars['interpolation.dir'] and self.api_conf.get('intertableDir'):
            self._vars['interpolation.dirs']['user'] = self.api_conf['intertableDir']

        self._vars['interpolation.latMap'] = interpolation_conf['latMap']
        self._vars['interpolation.lonMap'] = interpolation_conf['lonMap']
        self._vars['outMaps.unitTime'] = self.api_conf['OutMaps'].get('unitTime')

        # optional parameters (can also be defined by command line)
        if not self._vars['outMaps.namePrefix']:
            self._vars['outMaps.namePrefix'] = self.api_conf['OutMaps'].get('namePrefix') or self.api_conf['Parameter']['shortName']
        if self._vars['outMaps.scaleFactor'] is None:
            self._vars['outMaps.scaleFactor'] = self.api_conf['OutMaps'].get('scaleFactor') or 1.0
        if self._vars['outMaps.offset'] is None:
            self._vars['outMaps.offset'] = self.api_conf['OutMaps'].get('offset') or 0.0
        if self._vars['outMaps.validMin'] is None:
            self._vars['outMaps.validMin'] = self.api_conf['OutMaps'].get('validMin')
        if self._vars['outMaps.validMax'] is None:
            self._vars['outMaps.validMax'] = self.api_conf['OutMaps'].get('validMax')
        if self._vars['outMaps.valueFormat'] is None:
            self._vars['outMaps.valueFormat'] = self.api_conf['OutMaps'].get('valueFormat')
        if self._vars['outMaps.outputStepUnits'] is None:
            self._vars['outMaps.outputStepUnits'] = self.api_conf['OutMaps'].get('outputStepUnits')
        if self._vars['outMaps.fmap'] == 1:
            self._vars['outMaps.fmap'] = self.api_conf['OutMaps'].get('fmap') or 1
        if self._vars['outMaps.ext'] == 1:
            self._vars['outMaps.ext'] = self.api_conf['OutMaps'].get('ext') or 1

        # if start, end and dataTime are defined via command line input args, these are ignored.
        # if missing, GribReader will read all timesteps for the parameter
        if self._vars['parameter.tstart'] is None and self.api_conf['Parameter'].get('tstart'):
            self._vars['parameter.tstart'] = int(self.api_conf['Parameter']['tstart'])
        if self._vars['parameter.tend'] is None and self.api_conf['Parameter'].get('tend'):
            self._vars['parameter.tend'] = int(self.api_conf['Parameter']['tend'])
        if self._vars['parameter.dataTime'] is None and self.api_conf['Parameter'].get('dataTime'):
            self._vars['parameter.dataTime'] = int(self.api_conf['Parameter']['dataTime'])  # number
        if self._vars['parameter.dataDate'] is None and self.api_conf['Parameter'].get('dataDate'):
            self._vars['parameter.dataDate'] = int(self.api_conf['Parameter']['dataDate'])  # date

        self._vars['parameter.level'] = self.api_conf['Parameter'].get('level')  # number

        if self.api_conf.get('Aggregation'):
            self._vars['aggregation.step'] = self.api_conf['Aggregation'].get('step')
            self._vars['aggregation.type'] = self.api_conf['Aggregation'].get('type')

            self._vars['execution.doAggregation'] = bool(self._vars.get('aggregation.step')) and bool(self._vars.get('aggregation.type'))
            self._vars['aggregation.forceZeroArray'] = self._vars.get('aggregation.type') == ACCUMULATION and self.api_conf['Aggregation'].get('forceZeroArray', 'False').lower() not in strings.FALSE_STRINGS

        # string interpolation for custom user configurations (i.e. dataset folders)
        self.configuration.user.interpolate_strings(self)


class Pyg2pApi:
    """

    """

    @classmethod
    def parameter_details(cls, short_name=None):
        """

        :param short_name: shortName of the parameter for which you need to check configuration.
        :type short_name: str
        :return: details about parameter, conversion, unit etc. If short_name is not passed,
                 returns all shortNames of configured parameters
        :rtype: str
        """
        conf = Configuration().parameters
        if not short_name:
            res = conf._load()
            out = 'Available parameters short names: \n'
            out += '\n'.join(list(res.keys()))
            return out
        param = conf.get(short_name)
        out = f"Parameter {param['@shortName']}: {param['@description']} Unit: {param['@unit']}"
        conversions = param['Conversion']
        if not isinstance(conversions, list):
            conversions = [conversions]
        for c in conversions:
            out += '\n'
            out += f"Conversion id: {c['@id']} unit {c['@unit']} {c['@function']} [cut negative: {c['@cutOffNegative']}]"
        return out

    def __init__(self, api_ctx):
        """
        :param api_ctx: ApiContext instance
        """
        self.context = api_ctx
        self.interpolator = None
        self.messages = None
        self.values = None
        self.change_res_step = None
        clone = PCRasterReader(self.context.get('outMaps.clone'))
        self.mv = clone.mv
        rs = ma.masked_values(clone.values, self.mv)
        self._mask = ma.getmask(rs)

    def _mask_values(self, values):
        if isinstance(values, ma.core.MaskedArray):
            masked = ma.masked_where((self._mask | values.mask), values.data, copy=False)
        else:
            masked = ma.masked_where(self._mask, values, copy=False)
        masked = ma.filled(masked, self.mv)
        return masked

    def execute(self):
        """
        Main method
        :return: dict of numpy values, keys are instances of  pyg2p.Step
        """
        grib_reader = GRIBReader(self.context.get('input.file'), w_perturb=self.context.has_perturbation_number)
        grib_info = grib_reader.get_grib_info(self.context.create_select_cmd_for_aggregation_attrs())
        ctrl = Controller(self.context)
        ctrl.log_execution_context()
        values, self.messages, self.change_res_step = ctrl.execute(write_results=False)
        # need interpolation and correction
        self.interpolator = Interpolator(self.context, grib_info.mv)
        is_second_res = False
        lats, longs = self.messages.latlons
        geodetic_info = self.messages.grid_details
        grid_id = self.messages.grid_id
        out = {}
        for i, (timestep, v) in enumerate(values.items()):
            # note: timestep and change_res_step are instances of pyg2p.Step class
            if self.messages.have_resolution_change() and timestep == self.change_res_step:
                # Switching to second resolution
                lats, longs = self.messages.latlons_2nd
                geodetic_info = self.messages.grid_details.get_2nd_resolution()
                grid_id = self.messages.grid2_id
                is_second_res = True
            out_v = self.interpolator.interpolate(lats, longs, v, grid_id, geodetic_info, is_second_res=is_second_res)
            if self.context.must_do_correction:
                corrector = Corrector.get_instance(self.context, grid_id)
                out_v = corrector.correct(out_v)
            out_v = self._mask_values(out_v)
            out[timestep] = out_v
        out = collections.OrderedDict(sorted(out.items(), key=lambda item: int(item[0].end_step)))
        self.values = out
        return out
