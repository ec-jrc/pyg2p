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
    re_var = re.compile(r'{(?P<var>[a-zA-Z_]+)}')
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
                line = line.strip()
                if line and not line.startswith(self.comment_char):
                    key_value = line.split(self.sep)
                    props[key_value[0].strip()] = key_value[1].strip('" \t')
        return props

    def interpolate_strings(self, exe_ctx):
        """
        Change configuration strings in json commands files
        with user variables defined in ~/.pyg2p/*.conf files
        Strings like {CONF_DIR}/{MAPS_DIR}lat.map will be replaced with corresponding variables values
        exe_ctx: instance of ExecutionContext
        """
        vars_with_variables = [var for var in self.conf_to_interpolate if self.re_var.search(exe_ctx.get(var, ''))]
        for var in vars_with_variables:
            # we can have multiple variables {CONF_DIR}/{MAPS_DIR}lat.map
            exe_ctx[var] = exe_ctx[var].format(**self.vars)
            if self.re_var.search(exe_ctx[var]):
                # some variables where not string-interpolated so they are missing in user configuration
                vars_not_defined = self.re_var.findall(exe_ctx[var])
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
        logger.debug(f'Check configuration: [{self.__class__.__name__}]')
        if self.global_data_path_var:
            self.global_data_path = GlobalConf.get_instance(user_configuration).vars.get(self.global_data_path_var)
        if not self.only_global_conf:
            self.merge_with_user_conf()

    def load_global(self):
        try:
            res = self._load(resource_stream(pyg2p.__name__, self.global_config_file))
        except IOError:
            try:
                res = self._load(open(self.global_config_file_debug, 'r'))
            except IOError:
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
            raise ApplicationException.get_exc(EXISTING_GEOPOTENTIAL,
                                               details=f'{id_} for file {self.vars[id_]}. '
                                                       f'File was not added: {filepath}')

        name = file_util.filename(filepath)
        self.check_write()

        file_util.copy(filepath, self.data_path)
        self.user_vars[id_] = name
        self.dump()

    def remove(self, filename):
        for g in self.user_vars.keys():
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
            raise ApplicationException.get_exc(NO_FILE_GEOPOTENTIAL,
                                               details=f'id:{grid_id} {path} '
                                                       f'Searched in: {(self.data_path, self.global_data_path)}')
        return path


class IntertablesConfiguration(BaseConfiguration):
    config_file_ = 'intertables.json'
    data_path_var = UserConfiguration.intertables_path_var
    global_data_path_var = GlobalConf.intertables_path_var
    description = 'Config file for intertables. Do NOT edit this file!'


class Configuration(pyg2p.Loggable):

    def __init__(self):
        super().__init__()
        self.missing_config = []
        self.user = UserConfiguration()
        self.parameters = ParametersConfiguration(self.user)
        self.geopotentials = GeopotentialsConfiguration(self.user)
        self.intertables = IntertablesConfiguration(self.user)
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

    def download_data(self, dataset):

        remote_path = dataset
        local_path = getattr(self.user, '{}_path'.format(dataset))

        client = FTP(*self.ftp.access)
        self._log(f'=== Start downloading {remote_path} files to {local_path}', level='INFO')
        client.cwd(os.path.join(self.ftp.folder, remote_path))
        filenames = client.nlst()
        numfiles = len(filenames)
        for i, f in enumerate(filenames):
            if f in ('.', '..', 'readme.txt'):
                continue
            local_filename = os.path.join(local_path, f)
            if file_util.exists(local_filename):
                self._log(f'[{i}/{numfiles}] Skipping existing file {f}', level='INFO')
                continue
            self._log(f'[{i}/{numfiles}] Downloading {f}')
            with open(local_filename, 'wb') as local_file:
                client.retrbinary(f'RETR {f}', local_file.write)
        self._log(f'=== Download finished: {remote_path}')
        client.quit()  # close FTP connection

    def check_conf(self):
        # it logs all files in intertables and geopotentials paths that are not used in configuration

        used_intertables = [i['filename'] for i in self.intertables.vars.itervalues()]
        used_geopotentials = self.geopotentials.vars.values()

        intertables_folder_content = file_util.ls(self.intertables.data_path, 'npy')
        intertables_global_folder_content = file_util.ls(self.intertables.global_data_path, 'npy')
        geopotentials_folder_content = file_util.ls(self.geopotentials.data_path, 'npy')
        geopotentials_global_folder_content = file_util.ls(self.geopotentials.global_data_path, 'npy')
        for f in itertools.chain(intertables_folder_content, intertables_global_folder_content):
            if file_util.filename(f) not in used_intertables:
                self._log(f'Intertable file is not in configuration: {f} - You could delete it')

        for f in itertools.chain(geopotentials_folder_content, geopotentials_global_folder_content):
            if file_util.filename(f) not in used_geopotentials:
                self._log(f'Geopotential file is not in configuration: {f} - You could delete it')

        user_intertables = deepcopy(self.intertables.user_vars)
        for k, i in user_intertables.items():
            fullpath = os.path.join(self.intertables.data_path, i['filename'])
            if not file_util.exists(fullpath):
                self._log(f'{fullpath} - Non existing. Removing item from intertables.json')
                del self.intertables.user_vars[k]
        self.intertables.dump()
