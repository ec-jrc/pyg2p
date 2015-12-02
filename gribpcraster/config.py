import json
import os
from xmljson import badgerfish as bf
from xml.etree.ElementTree import fromstring

import util.files
from gribpcraster.application.readers.GRIBReader import GRIBReader
from gribpcraster.exc.ApplicationException import (
    ApplicationException,
    SHORTNAME_NOT_FOUND,
    CONVERSION_NOT_FOUND,
    NO_GEOPOTENTIAL
)


class UserConfiguration(object):
    user_conf_dir = '{}/{}'.format(os.path.expanduser('~'), '.pyg2p/')
    sep = '='
    comment_char = '#'

    def __init__(self):
        self.vars = {}
        if not util.files.exists(self.user_conf_dir, is_dir=True):
            util.files.create_dir(self.user_conf_dir)
        for f in os.listdir(self.user_conf_dir):
            filepath = os.path.join(self.user_conf_dir, f)
            if util.files.is_conf(filepath):
                self.vars.update(self.load_properties(filepath))

    def get(self, var):
        return self.vars.get(var)

    def load_properties(self, filepath):
        """
        Read the file passed as parameter as a properties file.
        """
        props = {}
        with open(filepath, "rt") as f:
            for line in f:
                l = line.strip()
                if l and not l.startswith(self.comment_char):
                    key_value = l.split(self.sep)
                    props[key_value[0].strip()] = key_value[1].strip('" \t')
        return props


class BaseConfiguration(object):
    config_file_ = ''
    data_path_ = ''

    def __init__(self, user_configuration):
        self.user_configuration = user_configuration
        self.config_file = os.path.join(user_configuration.user_conf_dir, self.config_file_)
        self.data_path = os.path.join(user_configuration.user_conf_dir, self.data_path_)
        self.vars = self.load()

    def load(self):
        with open(self.config_file) as f:
            return json.load(f)

    def dump(self):
        with open(self.config_file, 'w') as fh:
            fh.write(json.dumps(self.vars, sort_keys=True, indent=4))


class ParametersConfiguration(BaseConfiguration):
    config_file_ = 'parameters.json'

    def get(self, short_name):
        for param in self.vars['Parameters']['Parameter']:
            if param['@shortName'] == short_name:
                return param
        raise ApplicationException.get_programmatic_exc(SHORTNAME_NOT_FOUND, short_name)

    @staticmethod
    def get_conversion(parameter, id_):
        if isinstance(parameter.get('Conversion'), list):
            for conversion in parameter.get('Conversion'):
                if conversion['@id'] == id_:
                    return conversion
        elif isinstance(parameter.get('Conversion'), dict) and parameter['Conversion']['@id'] == id_:
            return parameter['Conversion']
        raise ApplicationException.get_programmatic_exc(CONVERSION_NOT_FOUND, '{} - {}'.format(parameter['@shortName'], id_))


class GeopotentialsConfiguration(BaseConfiguration):
    config_file_ = 'geopotentials.json'
    data_path_ = 'geopotentials'
    short_names = ['fis', 'z', 'FIS']

    def add(self, filepath):
        util.files.copy(filepath, self.data_path)
        args = {'shortName': self.short_names}
        id_ = GRIBReader.get_id(filepath, reader_args=args)
        name = util.files.file_name(filepath)
        self.vars['geopotentials']['geopotential'].append({'@id': id_, '@name': name})
        self.dump()

    def remove(self, filename):
        for g in self.vars['geopotentials']['geopotential']:
            if g['@name'] == filename:
                self.vars['geopotentials']['geopotential'].remove(g)
                self.dump()
                break

    def get_filepath(self, grid_id):
        for f in self.vars['geopotentials']['geopotential']:
            if f['@id'] == grid_id:
                return os.path.join(self.data_path, f['@name'])
        raise ApplicationException.get_programmatic_exc(NO_GEOPOTENTIAL, grid_id)


class Configuration(object):

    def __init__(self):
        self.user = UserConfiguration()
        self.parameters = ParametersConfiguration(self.user)
        self.geopotentials = GeopotentialsConfiguration(self.user)
        self.default_interpol_dir = os.path.join(self.user.user_conf_dir, 'intertables')

    def add_geopotential(self, filepath):
        self.geopotentials.add(filepath)

    def remove_geopotential(self, filename):
        self.geopotentials.remove(filename)

    @classmethod
    def convert_to_v2(cls, path):
        for f in os.listdir(path):
            filepath = os.path.join(path, f)
            if util.files.is_dir(filepath):
                cls.convert_to_v2(filepath)
            elif util.files.is_xml(filepath):
                with open(filepath) as f_:
                    res = bf.data(fromstring(f_.read()))
                    new_file = os.path.join(path, f.replace('.xml', '.json'))
                    new_file_ = open(new_file, 'w')
                    new_file_.write(json.dumps(res, sort_keys=True, indent=4))
                    new_file_.close()
