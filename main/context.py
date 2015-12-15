import argparse
import json
import os

import sys

import util.files
import util.strings
from main.exceptions import ApplicationException
from main.manipulation.aggregator import ACCUMULATION
from util.generics import now_string, FALSE_STRINGS

DEFAULT_VALUES = {'interpolation.mode': 'grib_nearest',
                  'outMaps.unitTime': '24'}


class ExecutionContext(object):
    def __init__(self, user_conf, argv):
        self._conf = user_conf
        self._input_args = {}
        self._to_add_geopotential = False
        self.input_file_with_geopotential = None
        self._vars = {}

        try:
            # read cli input args (commands file path, input files, output dir, or shows help and exit)
            self._define_input_args(argv)
            if not (self.add_geopotential or self.run_tests or self.convert_conf or self.copy_conf or self.convert_intertables):
                # read config files and define execuition parameters (set defaults also)
                self._define_exec_params()
        except Exception, err:
            raise ApplicationException(err, None, str(err))

        # check numbers, existing dirs and files, supported options, semantics etc.
        try:
            self._check_exec_params()
        except ValueError, err:
            raise ApplicationException(err, None, str(err))
        except Exception, exc:
            raise ApplicationException(exc, None, str(exc))

    def input_file_has_geopotential(self):
        self.input_file_with_geopotential = self.get('input.file')

    @property
    def interpolate_with_grib(self):
        return self._vars['interpolation.mode'].startswith('grib_')  # in ['grib_invdist', 'grib_nearest']

    def _define_input_args(self, argv):

        class ParserHelpOnError(argparse.ArgumentParser):
            def error(self, message):
                self.print_help()
                sys.stderr.write('Argument error: {}\n'.format(message))
                sys.exit(1)

        parser = ParserHelpOnError(description='''Execute the grib to pcraster conversion using parameters from the input xml configuration.
                                                        \n Read user and configuration manuals''')

        parser.add_argument('-c', '--commandsFile', help='/path/to/input/xml')
        parser.add_argument('-o', '--outDir', help='output maps dir', default='./')
        parser.add_argument('-i', '--inputFile', help='/path/to/input/grib')
        parser.add_argument('-I', '--inputFile2', help='/path/to/input/grib/2ndres/file')
        parser.add_argument('-s', '--start',
                            help='Grib timestep start. It overwrites the tstart in json execution file.', type=int)
        parser.add_argument('-e', '--end', help='Grib timestep end. It overwrites the tend in json execution file.',
                            type=int)

        parser.add_argument('-m', '--perturbationNumber', help='eps member number', type=int)

        parser.add_argument('-T', '--dataTime', help='To select messages by dataTime key value', type=int,
                            choices=['0', '1200'])
        parser.add_argument('-D', '--dataDate', help='<YYYYMMDD> to select messages by dataDate key value', type=int)

        parser.add_argument('-l', '--loggerLevel', help='Console logging level', default='INFO',
                            choices=['ERROR', 'WARNING', 'INFO', 'DEBUG'])
        parser.add_argument('-d', '--outLogDir', help='output logs dir', default='./logs/')
        parser.add_argument('-N', '--intertableDir', help='interpolation tables dir')
        parser.add_argument('-B', '--createIntertable', help='create intertable file',
                            action='store_true', default=False)

        parser.add_argument('-X', '--interpolationParallel', help='Use parallelization tools to make interpolation faster.'
                                                                  'If -B option is not passed or intertable already exists'
                                                                  ' it does not have any effect.',
                            action='store_true', default=False)

        parser.add_argument('-g', '--addGeopotential', help='''</path/to/geopotential/grib/file
        \nAdd the file to geopotentials.json configuration file, to use for correction.
        \nThe file will be copied into the right folder (configuration/geopotentials)
        \nNote: shortName of geopotential must be "fis" or "z"''')

        parser.add_argument('-t', '--test', help='''/path/to/test/xml_conf
        \nWill execute a battery of commands defined in configuration/tests/pyg2p_commands.txt
        \nand in configuration/tests/g2p_commands.txt. Then it will create diff pcraster maps and log alerts
        \nif differences are higher than a threshold''')

        parser.add_argument('-f', '--fmap', help='First map number', type=int, default=1)
        parser.add_argument('-x', '--ext', help='Extension number step', type=int, default=1)
        parser.add_argument('-n', '--namePrefix', help='Prefix name for maps')
        parser.add_argument('-C', '--convertConf', help='Convert old xml configuration to new json format')
        parser.add_argument('-z', '--convertIntertables', help='Convert old pyg2p intertables to new version (will overwrite!')
        parser.add_argument('-P', '--copyConf', help='Copy configuration from source to user folder (except intertables)',
                            action='store_true', default=False)
        if len(sys.argv) == 1:
            parser.print_help()
            sys.exit(0)

        parsed_args = vars(parser.parse_args(argv))

        self._vars['logger.level'] = parsed_args['loggerLevel']
        self._vars['logger.dir'] = parsed_args['outLogDir']

        self._input_args['commandsFile'] = parsed_args['commandsFile']
        self._vars['input.file'] = parsed_args['inputFile']
        self._vars['parameter.tstart'] = parsed_args['start']
        self._vars['parameter.tend'] = parsed_args['end']
        self._vars['parameter.dataTime'] = parsed_args['dataTime']
        self._vars['parameter.dataDate'] = parsed_args['dataDate']
        self._vars['interpolation.dir'] = parsed_args['intertableDir']
        self._vars['interpolation.create'] = parsed_args['createIntertable']
        self._vars['interpolation.parallel'] = parsed_args['interpolationParallel']
        self._vars['outMaps.fmap'] = parsed_args['fmap']
        self._vars['outMaps.ext'] = parsed_args['ext']
        self._vars['outMaps.namePrefix'] = parsed_args['namePrefix']
        self._vars['outMaps.outDir'] = parsed_args['outDir']
        self._vars['parameter.perturbationNumber'] = parsed_args['perturbationNumber']
        self._vars['input.file2'] = parsed_args['inputFile2']
        self._vars['input.two_resolution'] = bool(self._vars['input.file2'])
        self._vars['geopotential'] = parsed_args['addGeopotential']
        self._to_add_geopotential = bool(self._vars['geopotential'])
        self._vars['path_to_convert'] = parsed_args['convertConf']
        self._vars['path_to_intertables_to_convert'] = parsed_args['convertIntertables']
        self._vars['test.json'] = parsed_args['test']
        self._vars['copy_configuration'] = parsed_args['copyConf']

    def get(self, param, default=None):
        return self._vars.get(param, default) or default

    def __getitem__(self, param):
        return self._vars[param]

    def __setitem__(self, param, value):
        self._vars[param] = value

    # will read the json commands file and store parameters into a common dictionary
    def _define_exec_params(self):
        self._vars['execution.doAggregation'] = False
        self._vars['execution.doConversion'] = False
        self._vars['execution.doCorrection'] = False
        self._vars['parameter.conversionId'] = None

        if self._input_args['commandsFile'].startswith('./') or self._input_args['commandsFile'].startswith('../'):
            self._input_args['commandsFile'] = os.path.join(os.getcwd(), self._input_args['commandsFile'])

        if not util.files.exists(self._input_args['commandsFile']):
            raise ApplicationException.get_programmatic_exc(0, self._input_args['commandsFile'])

        with open(self._input_args['commandsFile']) as f:
            u = json.load(f)

        exec_conf = u['Execution']

        self._vars['execution.name'] = exec_conf['@name']

        self._vars['parameter.shortName'] = exec_conf['Parameter']['@shortName']
        parameter = self._conf.parameters.get(self._vars['parameter.shortName'])
        self._vars['parameter.description'] = parameter['@description']
        self._vars['parameter.unit'] = parameter['@unit']
        self._vars['parameter.conversionUnit'] = parameter['@unit']

        if exec_conf['Parameter'].get('@applyConversion'):
            self._vars['execution.doConversion'] = True
            self._vars['parameter.conversionId'] = exec_conf['Parameter']['@applyConversion']
            conversion = self._conf.parameters.get_conversion(parameter, self._vars['parameter.conversionId'])
            self._vars['parameter.conversionUnit'] = conversion['@unit']
            self._vars['parameter.conversionFunction'] = conversion['@function']
            self._vars['parameter.cutoffnegative'] = util.strings.to_boolean(conversion.get('@cutOffNegative'))

        if exec_conf['Parameter'].get('@correctionFormula') and exec_conf['Parameter'].get('@gem') and exec_conf['Parameter'].get('@demMap'):
            self._vars['execution.doCorrection'] = True
            self._vars['correction.formula'] = exec_conf['Parameter']['@correctionFormula']
            self._vars['correction.gemFormula'] = exec_conf['Parameter']['@gem']
            self._vars['correction.demMap'] = exec_conf['Parameter']['@demMap']

        self._vars['outMaps.clone'] = exec_conf['OutMaps']['@cloneMap']
        interpolation_conf = exec_conf['OutMaps']['Interpolation']
        self._vars['interpolation.mode'] = interpolation_conf.get('@mode', DEFAULT_VALUES['interpolation.mode'])
        if self._vars['interpolation.dir'] is None:
            # interlookup tables folder was not defined via command line with argument -N, --intertableDir
            # get from JSON or from default user configuration
            self._vars['interpolation.dir'] = interpolation_conf.get('@intertableDir', self._conf.default_interpol_dir)
        self._vars['interpolation.latMap'] = interpolation_conf['@latMap']
        self._vars['interpolation.lonMap'] = interpolation_conf['@lonMap']

        self._vars['outMaps.unitTime'] = exec_conf['OutMaps'].get('@unitTime')

        # optional parameters (can also be defined by command line)
        if not self._vars['outMaps.namePrefix']:
            self._vars['outMaps.namePrefix'] = exec_conf['OutMaps'].get('@namePrefix') or exec_conf['Parameter']['@shortName']
        if self._vars['outMaps.fmap'] == 1:
            self._vars['outMaps.fmap'] = exec_conf['OutMaps'].get('@fmap') or 1
        if self._vars['outMaps.ext'] == 1:
            self._vars['outMaps.ext'] = exec_conf['OutMaps'].get('@ext') or 1

        # if start, end and dataTime are defined via command line input args, these are ignored.
        # if missing, GribReader will read all timesteps for the parameter
        if self._vars['parameter.tstart'] is None and exec_conf['Parameter'].get('@tstart'):
            self._vars['parameter.tstart'] = int(exec_conf['Parameter']['@tstart'])
        if self._vars['parameter.tend'] is None and exec_conf['Parameter'].get('@tend'):
            self._vars['parameter.tend'] = int(exec_conf['Parameter']['@tend'])
        if self._vars['parameter.dataTime'] is None and exec_conf['Parameter'].get('@dataTime'):
            self._vars['parameter.dataTime'] = int(exec_conf['Parameter']['@dataTime'])  # number
        if self._vars['parameter.dataDate'] is None and exec_conf['Parameter'].get('@dataDate'):
            self._vars['parameter.dataDate'] = int(exec_conf['Parameter']['@dataDate'])  # date

        self._vars['parameter.level'] = exec_conf['Parameter'].get('@level')  # number

        if exec_conf.get('Aggregation'):
            self._vars['aggregation.step'] = exec_conf['Aggregation'].get('@step')
            self._vars['aggregation.type'] = exec_conf['Aggregation'].get('@type')
            self._vars['execution.doAggregation'] = bool(self._vars.get('aggregation.step')) and bool(self._vars.get('aggregation.type'))
            self._vars['aggregation.forceZeroArray'] = self._vars.get('aggregation.type') == ACCUMULATION and exec_conf['Aggregation'].get('@forceZeroArray', 'False') not in FALSE_STRINGS

        # string interpolation for custom user configurations (i.e. dataset folders)
        self._conf.user.interpolate_dirs(self)

    @property
    def must_do_aggregation(self):
        return self._vars['execution.doAggregation']

    @property
    def must_do_correction(self):
        return self._vars['execution.doCorrection']

    @property
    def must_do_conversion(self):
        return self._vars['execution.doConversion']

    def is_2_input_files(self):
        return self._vars['input.two_resolution']

    def _check_exec_params(self):

        if self.run_tests:
            if not util.files.exists(self._vars['test.json']):
                raise ApplicationException.get_programmatic_exc(7000, self._vars['test.json'])
        elif self.add_geopotential:
            if not util.files.exists(self._vars['geopotential']):
                raise ApplicationException.get_programmatic_exc(7001, self._vars['geopotential'])
        elif self.convert_conf:
            if not util.files.exists(self._vars['path_to_convert'], is_folder=True):
                raise ApplicationException.get_programmatic_exc(7002, self._vars['path_to_convert'])
        elif self.copy_conf:
            pass
        elif self.convert_intertables:
            if not util.files.exists(self._vars['path_to_intertables_to_convert'], is_folder=True):
                raise ApplicationException.get_programmatic_exc(7003, self._vars['path_to_intertables_to_convert'])
        else:

            if not self._vars.get('input.file'):
                raise ApplicationException.get_programmatic_exc(1001)
            if not util.files.exists(self._vars['input.file']):
                raise ApplicationException.get_programmatic_exc(1000, self._vars['input.file'])
            if not util.files.exists(self._vars['interpolation.lonMap']) or not util.files.exists(self._vars['interpolation.latMap']):
                raise ApplicationException.get_programmatic_exc(1300)
            if not util.files.exists(self._vars['outMaps.clone']):
                raise ApplicationException.get_programmatic_exc(1310)

            # create out dir if not existing
            try:
                if self._vars['outMaps.outDir'] != './':
                    if not self._vars['outMaps.outDir'].endswith('/'):
                        self._vars['outMaps.outDir'] += '/'
                    if not util.files.exists(self._vars['outMaps.outDir'], is_folder=True):
                        util.files.create_dir(self._vars['outMaps.outDir'])
            except Exception, exc:
                raise ApplicationException(exc, None, str(exc))

            if self._vars.get('interpolation.dir') and not util.files.exists(self._vars['interpolation.dir'], is_folder=True):
                raise ApplicationException.get_programmatic_exc(1320, self._vars['interpolation.dir'])

            # check all numbers

            if self._vars['parameter.level'] and not self._vars['parameter.level'].isdigit():
                raise ApplicationException.get_programmatic_exc(1400, 'Parameter level')
            self._vars['parameter.level'] = int(self._vars['parameter.level']) if self._vars.get('parameter.level') else None

            self._vars['outMaps.unitTime'] = int(self._vars['outMaps.unitTime']) if self._vars['outMaps.unitTime'] is not None else DEFAULT_VALUES['outMaps.unitTime']

            # check tstart<=tend
            if self._vars['parameter.tstart'] and self._vars['parameter.tend'] and not self._vars['parameter.tstart'] <= self._vars['parameter.tend']:
                raise ApplicationException.get_programmatic_exc(1500)

            # check both correction params are present
            if self._vars['execution.doCorrection'] and not (self._vars.get('correction.gemFormula') and self._vars.get('correction.demMap') and self._vars.get('correction.formula')):
                raise ApplicationException.get_programmatic_exc(4100)
            if self._vars['execution.doCorrection'] and not util.files.exists(self._vars['correction.demMap']):
                raise ApplicationException.get_programmatic_exc(4200, self._vars['correction.demMap'])

    def __str__(self):
        mess = '\n\n============ pyg2p: Execution parameters: {} {} ============\n\n'.format(self._vars['execution.name'], now_string())
        params_str = ['{}={}'.format(par, self._vars[par]) for par in sorted(self._vars.iterkeys()) if self._vars[par]]
        return '{}{}'.format(mess, '\n'.join(params_str))

    @property
    def add_geopotential(self):
        return self._to_add_geopotential

    def has_perturbation_number(self):
        return 'parameter.perturbationNumber' in self._vars and self._vars['parameter.perturbationNumber'] is not None

    def create_select_cmd_for_reader(self, start_, end_):

        # 'var' suffix is for multiresolution 240 step message (global EUE files)
        reader_args = {
            'shortName': [str(self._vars['parameter.shortName']), str(self._vars['parameter.shortName']).upper(),
                          str(self._vars['parameter.shortName'] + 'var')]}

        if self._vars['parameter.level'] is not None:
            reader_args['level'] = self._vars['parameter.level']
        if self._vars['parameter.dataTime'] is not None:
            reader_args['dataTime'] = self._vars['parameter.dataTime']
        if self._vars['parameter.dataDate'] is not None:
            reader_args['dataDate'] = self._vars['parameter.dataDate']

        if self.has_perturbation_number():
            reader_args['perturbationNumber'] = self._vars['parameter.perturbationNumber']

        # start_step, end_step
        if start_ == end_:
            reader_args['endStep'] = end_
            reader_args['startStep'] = start_
        else:
            reader_args['endStep'] = lambda s: s <= end_
            reader_args['startStep'] = lambda s: s >= start_
        return reader_args

    def create_select_cmd_for_aggregation_attrs(self):

        reader_arguments = {'shortName': str(self._vars['parameter.shortName'])}
        if 'parameter.perturbationNumber' in self._vars and self._vars['parameter.perturbationNumber'] is not None:
            reader_arguments['perturbationNumber'] = self._vars['parameter.perturbationNumber']
        return reader_arguments

    @property
    def run_tests(self):
        return bool(self._vars.get('test.json'))

    @property
    def convert_conf(self):
        return bool(self._vars.get('path_to_convert'))

    @property
    def convert_intertables(self):
        return bool(self._vars.get('path_to_intertables_to_convert'))

    @property
    def copy_conf(self):
        return bool(self._vars.get('copy_configuration'))

    def geo_file(self, grid_id):
        return self.input_file_with_geopotential or self._conf.geopotentials.get_filepath(grid_id)
        # return self._conf.geopotentials.get_filepath(grid_id)
