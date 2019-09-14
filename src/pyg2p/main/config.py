import json
import os
import logging
import re
from copy import deepcopy
from ftplib import FTP
import itertools
from pkg_resources import resource_stream

import pyg2p
from pyg2p.main.readers.grib import GRIBReader
from pyg2p.main.exceptions import (
    ApplicationException,
    SHORTNAME_NOT_FOUND,
    CONVERSION_NOT_FOUND,
    NO_GEOPOTENTIAL,
    NO_VAR_DEFINED, JSON_ERROR, EXISTING_GEOPOTENTIAL,
    NO_WRITE_PERMISSIONS, NOT_EXISTING_PATH, NO_FILE_GEOPOTENTIAL, NO_READ_PERMISSIONS)

import pyg2p.util.files as file_util
# from pyg2p.util.logger import Logger


class UserConfiguration(object):
    """
    Class that holds all values defined in properties .conf files under ~/.pyg2p/ folder
    These variables are used to interpolate .json command files.
    Ex: in a json command file you can define "@latMap": "{EFAS_MAPS}/lat.map"
    and in ~/pyg2p/mysettings.conf you set EFAS_MAPS=/path/to/my/maps
    """
    config_dir = '{}/{}'.format(os.path.expanduser('~'), '.pyg2p/')
    sep = '='
    comment_char = '#'
    conf_to_interpolate = ('correction.demMap', 'outMaps.clone', 'interpolation.latMap', 'interpolation.lonMap')
    regex_var = re.compile(r'{(?P<var>[a-zA-Z_]+)}')
    geopotentials_path_var = 'GEOPOTENTIALS'
    intertables_path_var = 'INTERTABLES'

    def __init__(self):
        self.vars = {}
        # create user folder .pyg2p always
        if not file_util.exists(self.config_dir, is_folder=True):
            file_util.create_dir(self.config_dir)
        for f in os.listdir(self.config_dir):
            filepath = os.path.join(self.config_dir, f)
            if file_util.is_conf(filepath):
                self.vars.update(self.load_properties(filepath))

        self.geopotentials_path = self.get(self.geopotentials_path_var)
        self.intertables_path = self.get(self.intertables_path_var)

    def get(self, var):
        return self.vars.get(var)

    def load_properties(self, filepath):
        props = {}
        with open(filepath, "rt") as f:
            for line in f:
                l = line.strip()
                if l and not l.startswith(self.comment_char):
                    key_value = l.split(self.sep)
                    props[key_value[0].strip()] = key_value[1].strip('" \t')
        return props

    def interpolate_strings(self, execution_context):
        """
        Change configuration strings in json commands files
        with user variables defined in ~/.pyg2p/*.conf files
        Strings like {CONF_DIR}/{MAPS_DIR}lat.map will be replaced with corresponding variables values
        execution_context: instance of ExecutionContext
        """
        vars_with_variables = [var for var in self.conf_to_interpolate if self.regex_var.search(execution_context.get(var, ''))]
        for var in vars_with_variables:
            # we can have multiple variables {CONF_DIR}/{MAPS_DIR}lat.map
            execution_context[var] = execution_context[var].format(**self.vars)
            if self.regex_var.search(execution_context[var]):
                # some variables where not string-interpolated so they are missing in user configuration
                vars_not_defined = self.regex_var.findall(execution_context[var])
                raise ApplicationException.get_exc(NO_VAR_DEFINED, str(vars_not_defined))


class BaseConfiguration(object):
    config_file_ = ''
    data_path_var = ''
    global_data_path_var = ''
    description = ''
    init_dict = {}
    only_global_conf = False
    instance = None
    GLOBAL_CONFIG_DIR = 'configuration/'  # data dir in package to read as resource stream

    def __init__(self, user_configuration):

        self.configuration_mode = False
        self.user_configuration = user_configuration
        self.config_file = os.path.join(user_configuration.config_dir, self.config_file_)
        self.global_config_file = os.path.join(self.GLOBAL_CONFIG_DIR, self.config_file_)
        self.global_config_file_debug = os.path.join(self.GLOBAL_CONFIG_DIR, 'global/', self.config_file_)
        self.data_path = user_configuration.get(self.data_path_var)
        self.vars = self.load_global()
        self.user_vars = {}
        logger = logging.getLogger()
        logger.info('Check configuration: [{}]'.format(self.__class__.__name__))
        if self.global_data_path_var:
            self.global_data_path = GlobalConf.get_instance(user_configuration).vars.get(self.global_data_path_var)
            if not file_util.can_read(self.global_data_path):
                raise ApplicationException.get_exc(NO_READ_PERMISSIONS, details='{}'.format(self.global_data_path))
        if not self.only_global_conf:
            self.merge_with_user_conf()

    def load_global(self):
        try:
            res = self._load(resource_stream(pyg2p.__name__, self.global_config_file))
        except IOError:
            try:
                res = self._load(open(self.global_config_file_debug, 'r'))
            except IOError as e:
                res = {}
        return res

    def merge_with_user_conf(self):
        # it overwrites global config. If not config file for user is found, it creates an empty one.
        if not file_util.exists(self.config_file):
            self.user_vars = {'description': self.description}
            if self.init_dict:
                self.user_vars.update(self.init_dict)
            self.dump()
        else:
            self.user_vars = self._load()
        self.vars.update(self.user_vars)

    def _load(self, config_file=None):
        f = open(self.config_file) if not config_file else config_file
        try:
            content = json.load(f)
        except ValueError as e:
            raise ApplicationException.get_exc(JSON_ERROR, details='{} {}'.format(e, self.config_file))
        else:
            return content
        finally:
            f.close()

    def dump(self):
        with open(self.config_file, 'w') as f:
            user_vars = self.user_vars or '{}'
            f.write(json.dumps(user_vars, sort_keys=True, indent=4))

    def check_write(self):

        if not self.data_path:
            # user hasn't defined his own data folder for geopotentials.
            raise ApplicationException.get_exc(NO_VAR_DEFINED, self.data_path_var)
        if not file_util.exists(self.data_path, is_folder=True):
            raise ApplicationException.get_exc(NOT_EXISTING_PATH, self.data_path)
        if not file_util.can_write(self.data_path):
            raise ApplicationException.get_exc(NO_WRITE_PERMISSIONS, self.data_path)


class GlobalConf(BaseConfiguration):
    config_file_ = 'global_conf.json'
    only_global_conf = True
    geopotentials_path_var = 'geopotentials'
    intertables_path_var = 'intertables'

    @classmethod
    def get_instance(cls, user_configuration):
        if cls.instance:
            return cls.instance
        cls.instance = GlobalConf(user_configuration)
        return cls.instance

    @property
    def geopotential_path(self):
        return self.vars.get('geopotentials')

    @property
    def intertable_path(self):
        return self.vars.get('intertables')


class FtpConfig(BaseConfiguration):
    config_file_ = 'ftp.json'
    description = 'Put here your FTP host, user credentials and remote folder'
    init_dict = {'host': '', 'folder': '', 'user': '', 'pwd': ''}

    @property
    def access(self):
        return self.vars.get('host'), self.vars.get('user'), self.vars.get('pwd')

    @property
    def folder(self):
        return self.vars.get('folder')


class ParametersConfiguration(BaseConfiguration):
    config_file_ = 'parameters.json'
    description = 'Set here new parameters to extract. See example.'
    init_dict = {'xyz': {
        '@description': "var description",
        '@shortName': "xyz",
        "@unit": "xyz_unit_string",
        "Conversion": {
            "@function": "x=x",
            "@id": "xyz_conversion_id",
            "@unit": "xyz_converted_unit"
        }
    }}

    def get(self, short_name):
        param = self.vars.get(short_name)
        if not param:
            raise ApplicationException.get_exc(SHORTNAME_NOT_FOUND, short_name)
        return param

    @staticmethod
    def get_conversion(parameter, id_):
        if isinstance(parameter.get('Conversion'), list):
            for conversion in parameter.get('Conversion'):
                if conversion['@id'] == id_:
                    return conversion
        elif isinstance(parameter.get('Conversion'), dict) and parameter['Conversion']['@id'] == id_:
            return parameter['Conversion']
        raise ApplicationException.get_exc(CONVERSION_NOT_FOUND, '{} - {}'.format(parameter['@shortName'], id_))


class GeopotentialsConfiguration(BaseConfiguration):
    config_file_ = 'geopotentials.json'
    data_path_var = UserConfiguration.geopotentials_path_var
    global_data_path_var = GlobalConf.geopotentials_path_var
    short_names = ['fis', 'z', 'FIS', 'orog']
    description = 'Config file for geopotentials. Do NOT edit this file!'

    def add(self, filepath):
        args = {'shortName': self.short_names}
        id_ = GRIBReader.get_id(filepath, reader_args=args)
        if id_ in self.vars:
            raise ApplicationException.get_exc(EXISTING_GEOPOTENTIAL, details='{} for file {}. File was not added: {}'.format(id_, self.vars[id_], filepath))

        name = file_util.filename(filepath)
        self.check_write()

        file_util.copy(filepath, self.data_path)
        self.user_vars[id_] = name
        self.dump()

    def remove(self, filename):
        for g in self.user_vars.iterkeys():
            if self.user_vars[g] == filename:
                del self.user_vars[g]
                self.dump()
                break

    def get_filepath(self, grid_id):
        filename = self.vars.get(grid_id)
        if not filename:
            raise ApplicationException.get_exc(NO_GEOPOTENTIAL, grid_id)
        path = None if not self.data_path else os.path.join(self.data_path, filename)
        if not path or not file_util.exists(path):
            path = os.path.join(self.global_data_path, filename)
        if not file_util.exists(path):
            raise ApplicationException.get_exc(NO_FILE_GEOPOTENTIAL, details='id:{} {} Searched in: {}'.format(grid_id, path, (self.data_path, self.global_data_path)))
        return path


class IntertablesConfiguration(BaseConfiguration):
    config_file_ = 'intertables.json'
    data_path_var = UserConfiguration.intertables_path_var
    global_data_path_var = GlobalConf.intertables_path_var
    description = 'Config file for intertables. Do NOT edit this file!'


class TestsConfiguration(BaseConfiguration):
    config_file_ = 'test.json'
    description = 'Config file for tests. Set paths to executables here.'
    init_dict = {'TestConfiguration': {'atol': 0.05,
                                       'PcRasterDiff': os.path.join(os.getenv('PCRASTER_HOME', '/opt/pcraster'), '/bin/pcrcalc'),
                                       'g2p': os.getenv('GRIB2PCRASTER', '/usr/local/bin/grib2pcraster'),
                                       }
                 }


class Configuration(object):

    def __init__(self):
        self.missing_config = []
        self.user = UserConfiguration()
        self.parameters = ParametersConfiguration(self.user)
        self.geopotentials = GeopotentialsConfiguration(self.user)
        self.intertables = IntertablesConfiguration(self.user)
        self.tests = TestsConfiguration(self.user)
        self.ftp = FtpConfig(self.user)
        self.default_interpol_dir = self.intertables.data_path
        for conf in (self.parameters, self.geopotentials, self.intertables):
            if not conf.configuration_mode:
                continue
            self.missing_config.append(conf.config_file)

    def add_geopotential(self, filepath):
        self.geopotentials.add(filepath)

    def remove_geopotential(self, filename):
        self.geopotentials.remove(filename)

    @classmethod
    def convert_geopotentials(cls, data):
        new_data = {}
        for p in data['geopotentials']['geopotential']:
            new_data[p['@id']] = p['@name']
        return new_data

    @classmethod
    def convert_parameters(cls, data):
        new_data = {}
        for p in data['Parameters']['Parameter']:
            new_data[p['@shortName']] = p
        return new_data

    def download_data(self, dataset, logger):

        logger.attach_config_logger()
        remote_path = dataset
        local_path = getattr(self.user, '{}_path'.format(dataset))

        client = FTP(*self.ftp.access)
        logger.info('=== Start downloading {} files to {}'.format(remote_path, local_path))
        client.cwd(os.path.join(self.ftp.folder, remote_path))
        filenames = client.nlst()
        numfiles = len(filenames)
        for i, f in enumerate(filenames):
            if f in ('.', '..', 'readme.txt'):
                continue
            local_filename = os.path.join(local_path, f)
            if file_util.exists(local_filename):
                logger.info('[{}/{}] Skipping existing file {}'.format(i, numfiles, f))
                continue
            logger.info('[{}/{}] Downloading {}'.format(i, numfiles, f))
            with open(local_filename, 'wb') as local_file:
                client.retrbinary('RETR {}'.format(f), local_file.write)
        logger.info('=== Download finished: {}'.format(remote_path))
        client.quit()  # close FTP connection
        logger.detach_config_logger()

    def convert_intertables_to_v2(self, path, logger):
        # convert files in a path and copy into user intertables folder
        import numpy as np
        logger.attach_config_logger()
        logger.info('Looking into {}. \nNote: Old GRIB_API intertables of rotated grids and scipy intertables cannot be converted and will be skipped'.format(path))
        existing_intertables = [i['filename'] for i in self.intertables.vars.itervalues()]

        for f in os.listdir(path):
            filepath = os.path.join(path, f)
            if file_util.is_dir(filepath):
                self.convert_intertables_to_v2(filepath, logger)

            elif f.endswith('.npy') and not f.startswith('tbl_') and f not in existing_intertables:
                # This must be a pyg2p v1 intertable...
                if 'rotated' in f or '_scipy_' in f:
                    logger.info('Skipped: {}. Scipy intertables and old rotated GRIB_API interpolated grids are not valid anymore.'.format(f))
                    continue

                # v2 intertable_id is v1 intertable filename without npy extension (and with _M_ instead of _MISSING_)
                intertable_id = file_util.without_ext(f).replace('_MISSING_', '_M_')

                existing_intertable_path = ''
                if intertable_id in self.intertables.vars:
                    existing = False
                    for path_ in (self.intertables.data_path, self.intertables.global_data_path):
                        existing_intertable_path = os.path.join(path_, self.intertables.vars[intertable_id]['filename'])
                        if file_util.exists(existing_intertable_path):
                            existing = True
                            logger.info('Skipped: {}. You already have a V2 intertable in intertable folder {}'.format(f, existing_intertable_path))
                            break
                    if existing:
                        # skip file
                        continue
                    # if not existing file but existing id and filename in configuration, we use same filename to user path
                    existing_intertable_path = os.path.join(self.intertables.data_path, self.intertables.vars[intertable_id]['filename'])

                def tbl_new_path(sfx):
                    if existing_intertable_path:
                        # we will use the filename already in configuration (but the real npy file is missing)
                        return existing_intertable_path
                    tokens = f.split('_')
                    source_res = tokens[3]
                    source_grid = '{}_{}'.format(tokens[5], tokens[6])
                    _filename = 'tbl{nprog}_{res}_{grid}{suffix}.npy'.format(nprog='', res=source_res,
                                                                             grid=source_grid, suffix=sfx)
                    _path = os.path.join(self.intertables.data_path, _filename)
                    _i = 0
                    while file_util.exists(_path):
                        _i += 1
                        _filename = 'tbl{nprog}_{res}_{grid}{suffix}.npy'.format(nprog='_{}'.format(_i), res=source_res,
                                                                                 grid=source_grid, suffix=sfx)
                        _path = os.path.join(self.intertables.data_path, _filename)
                    return _path

                intertable = np.load(filepath)

                if f.endswith('_nn.npy'):
                    suffix = '_grib_nearest'
                    new_full_path = tbl_new_path(suffix)
                    # convert grib nn
                    xs = intertable[0].astype(int, copy=False)
                    ys = intertable[1].astype(int, copy=False)
                    indexes = intertable[2].astype(int, copy=False)
                    intertable = np.asarray([xs, ys, indexes])
                    np.save(new_full_path, intertable)
                    self.intertables.user_vars[intertable_id] = {'filename': file_util.filename(new_full_path),
                                                                 'method': 'grib_nearest',
                                                                 'source_shape': 'NA',
                                                                 'target_shape': 'NA',
                                                                 'info': 'Converted from v1'}
                    logger.info('Converted and saved to: {}'.format(file_util.filename(new_full_path)))

                elif f.endswith('_inv.npy'):
                    # convert grib invdist
                    suffix = '_grib_invdist'
                    new_full_path = tbl_new_path(suffix)

                    try:
                        intertable['indexes']
                    except IndexError:
                        # in version 1 indexes were stored as float
                        xs = intertable[0].astype(int, copy=False)
                        ys = intertable[1].astype(int, copy=False)
                        idxs1 = intertable[2].astype(int, copy=False)
                        idxs2 = intertable[3].astype(int, copy=False)
                        idxs3 = intertable[4].astype(int, copy=False)
                        idxs4 = intertable[5].astype(int, copy=False)
                        coeffs1 = intertable[6]
                        coeffs2 = intertable[7]
                        coeffs3 = intertable[8]
                        coeffs4 = intertable[9]

                        indexes = np.asarray([xs, ys, idxs1, idxs2, idxs3, idxs4])
                        coeffs = np.asarray([coeffs1, coeffs2, coeffs3, coeffs4, np.zeros(coeffs1.shape), np.zeros(coeffs1.shape)])
                        intertable = np.rec.fromarrays((indexes, coeffs), names=('indexes', 'coeffs'))

                    np.save(new_full_path, intertable)
                    self.intertables.user_vars[intertable_id] = {'filename': file_util.filename(new_full_path),
                                                                 'method': 'grib_invdist',
                                                                 'source_shape': 'NA',
                                                                 'target_shape': 'NA',
                                                                 'info': 'Converted from v1'}
                    logger.info('Converted and saved to: {}'.format(file_util.filename(new_full_path)))

        # update config dict to intertables.json
        self.intertables.dump()
        logger.detach_config_logger()

    def check_conf(self, logger):
        # it logs all files in intertables and geopotentials paths that are not used in configuration
        logger.attach_config_logger()

        used_intertables = [i['filename'] for i in self.intertables.vars.itervalues()]
        used_geopotentials = self.geopotentials.vars.values()

        intertables_folder_content = file_util.ls(self.intertables.data_path, 'npy')
        intertables_global_folder_content = file_util.ls(self.intertables.global_data_path, 'npy')
        geopotentials_folder_content = file_util.ls(self.geopotentials.data_path, 'npy')
        geopotentials_global_folder_content = file_util.ls(self.geopotentials.global_data_path, 'npy')
        for f in itertools.chain(intertables_folder_content, intertables_global_folder_content):
            if file_util.filename(f) not in used_intertables:
                logger.info('Intertable file is not in configuration: {} - You could delete it'.format(f))

        for f in itertools.chain(geopotentials_folder_content, geopotentials_global_folder_content):
            if file_util.filename(f) not in used_geopotentials:
                logger.info('Geopotential file is not in configuration: {} - You could delete it'.format(f))

        user_intertables = deepcopy(self.intertables.user_vars)
        for k, i in user_intertables.items():
            fullpath = os.path.join(self.intertables.data_path, i['filename'])
            if not file_util.exists(fullpath):
                logger.info('{} - Non existing. Removing item from intertables.json'.format(fullpath))
                del self.intertables.user_vars[k]
        self.intertables.dump()

        logger.detach_config_logger()
