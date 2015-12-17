import json
import os
import re
from xml.etree.ElementTree import fromstring

from xmljson import badgerfish as bf

import util.files
from main.exceptions import (
    ApplicationException,
    SHORTNAME_NOT_FOUND,
    CONVERSION_NOT_FOUND,
    NO_GEOPOTENTIAL,
    NO_VAR_DEFINED, JSON_ERROR, EXISTING_GEOPOTENTIAL)
from main.readers.grib import GRIBReader


class UserConfiguration(object):
    """
    Class that holds all values defined in properties .conf files under ~/.pyg2p/ folder
    These variables are used to interpolate .json command files.
    Ex: in a json command file you can define "@latMap": "{EFAS_MAPS}/lat.map"
    and in ~/pyg2p/mysettings.conf you set EFAS_MAPS=/path/to/my/maps
    """
    user_conf_dir = '{}/{}'.format(os.path.expanduser('~'), '.pyg2p/')
    sep = '='
    comment_char = '#'
    to_interpolate = ('correction.demMap', 'outMaps.clone', 'interpolation.latMap', 'interpolation.lonMap')
    regex = re.compile(r'{(?P<var>[a-zA-Z_]+)}')

    def __init__(self):
        self.vars = {}
        if not util.files.exists(self.user_conf_dir, is_folder=True):
            util.files.create_dir(self.user_conf_dir)
        for f in os.listdir(self.user_conf_dir):
            filepath = os.path.join(self.user_conf_dir, f)
            if util.files.is_conf(filepath):
                self.vars.update(self.load_properties(filepath))

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

    def _interpolate_strings(self, execution_context):
        """
        Change configuration strings in json commands files
        with user variables defined in ~/.pyg2p/*.conf files
        Strings like {CONF_DIR}/{MAPS_DIR}lat.map will be replaced with corresponding variables values
        execution_context: instance of ExecutionContext
        """
        vars_with_variables = [var for var in self.to_interpolate if self.regex.search(execution_context.get(var, ''))]
        for var in vars_with_variables:
            # we can have multiple variables {CONF_DIR}/{MAPS_DIR}lat.map
            execution_context[var] = execution_context[var].format(**self.vars)
            if self.regex.search(execution_context[var]):
                # some variables where not string-interpolated so they are missing in user configuration
                vars_not_defined = self.regex.findall(execution_context[var])
                raise ApplicationException.get_programmatic_exc(NO_VAR_DEFINED, str(vars_not_defined))


class BaseConfiguration(object):
    config_file_ = ''
    data_path_ = ''

    def __init__(self, user_configuration):
        self.configuration_mode = False
        self.user_configuration = user_configuration
        self.config_file = os.path.join(user_configuration.user_conf_dir, self.config_file_)
        self.data_path = os.path.join(user_configuration.user_conf_dir, self.data_path_)
        if util.files.exists(self.config_file):
            self.vars = self.load()
        else:
            self.configuration_mode = True

    def load(self):
        with open(self.config_file) as f:
            try:
                content = json.load(f)
            except ValueError as e:
                raise ApplicationException.get_programmatic_exc(JSON_ERROR, details='{} {}'.format(e, self.config_file))
        return content

    def dump(self, new_dict=None):
        with open(self.config_file, 'w') as fh:
            fh.write(json.dumps(self.vars if not new_dict else new_dict, sort_keys=True, indent=4))


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

        args = {'shortName': self.short_names}
        id_ = GRIBReader.get_id(filepath, reader_args=args)
        for item in self.vars['geopotentials']['geopotential']:
            if item['@id'] == id_:
                name = item['@name']
                raise ApplicationException.get_programmatic_exc(EXISTING_GEOPOTENTIAL, details='{} for file {}. File was not added: {}'.format(id_, name, filepath))
        name = util.files.filename(filepath)
        util.files.copy(filepath, self.data_path)
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


class IntertablesConfiguration(BaseConfiguration):
    config_file_ = 'intertables.json'
    data_path_ = 'intertables'


class Configuration(object):

    def __init__(self):
        self.configuration_mode = False
        self.user = UserConfiguration()
        self.parameters = ParametersConfiguration(self.user)
        self.geopotentials = GeopotentialsConfiguration(self.user)
        self.intertables = IntertablesConfiguration(self.user)
        self.default_interpol_dir = self.intertables.data_path
        if any([self.parameters.configuration_mode, self.geopotentials.configuration_mode, self.intertables.configuration_mode]):
            self.configuration_mode = True

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

    def copy_source_configuration(self, logger):
        logger.attach_config_logger()
        target_dir = self.user.user_conf_dir
        source_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../configuration')
        geopotentials_json = os.path.join(source_dir, GeopotentialsConfiguration.config_file_)
        geopotentials_data = os.path.join(source_dir, GeopotentialsConfiguration.data_path_)
        parameters_json = os.path.join(source_dir, ParametersConfiguration.config_file_)
        intertables_json = os.path.join(source_dir, IntertablesConfiguration.config_file_)
        tests_conf_dir = os.path.join(source_dir, 'tests')

        util.files.copy(parameters_json, target_dir)
        util.files.copy(intertables_json, target_dir)
        util.files.copy_dir(tests_conf_dir, os.path.join(target_dir, 'tests'), recreate=True)
        util.files.copy(geopotentials_json, target_dir)
        logger.info('Copying geopotentials grib files to {}'.format(os.path.join(target_dir, GeopotentialsConfiguration.data_path_)))
        util.files.copy_dir(geopotentials_data, os.path.join(target_dir, GeopotentialsConfiguration.data_path_))
        logger.detach_config_logger()

    def convert_intertables_to_v2(self, path, logger):
        # convert files in a path and copy into user intertables folder
        import numpy as np
        logger.attach_config_logger()
        logger.info('Looking into {}'.format(path))
        intertables_dict = self.intertables.vars
        existing_intertables = [i['filename'] for i in intertables_dict.itervalues()]

        for f in os.listdir(path):
            filepath = os.path.join(path, f)
            if util.files.is_dir(filepath):
                self.convert_intertables_to_v2(filepath, logger)
            elif f.endswith('.npy') and not f.startswith('tbl_') and f not in existing_intertables:
                # This must be a pyg2p v1 intertable...

                intertable_id = util.files.without_ext(f).replace('_MISSING_', '_M_')  # v2 id is v1 intertable filename
                if intertable_id in intertables_dict:
                    existing_intertable = os.path.join(self.intertables.data_path, intertables_dict[intertable_id]['filename'])
                    if util.files.exists(existing_intertable):
                        logger.info('Skipped: {}. You already have a V2 intertable in your intertable folder {}'.format(f, existing_intertable))
                        continue

                def tbl_new_path(sfx):
                    tokens = f.split('_')
                    source_res = tokens[3]
                    source_grid = '{}_{}'.format(tokens[5], tokens[6])
                    _filename = 'tbl{nprog}_{res}_{grid}{suffix}.npy'.format(nprog='', res=source_res,
                                                                             grid=source_grid, suffix=sfx)
                    _path = os.path.join(self.intertables.data_path, _filename)
                    _i = 0
                    while util.files.exists(_path):
                        _i += 1
                        _filename = 'tbl{nprog}_{res}_{grid}{suffix}.npy'.format(nprog='_{}'.format(_i), res=source_res,
                                                                                 grid=source_grid, suffix=sfx)
                        _path = os.path.join(self.intertables.data_path, _filename)
                    return _path

                intertable = np.load(filepath)

                if f.endswith('_nn.npy'):
                    suffix = '_nn'
                    new_full_path = tbl_new_path(suffix)
                    # convert grib nn
                    xs = intertable[0].astype(int, copy=False)
                    ys = intertable[1].astype(int, copy=False)
                    indexes = intertable[2].astype(int, copy=False)
                    intertable = np.asarray([xs, ys, indexes])
                    np.save(new_full_path, intertable)
                    intertables_dict[intertable_id] = {'filename': util.files.filename(new_full_path),
                                                       'method': 'grib_nearest',
                                                       'source_shape': 'NA',
                                                       'target_shape': 'NA',
                                                       'info': 'Converted from v1'}
                    logger.info('Converted and saved to: {}'.format(util.files.filename(new_full_path)))

                elif f.endswith('_inv.npy'):
                    # convert grib invdist
                    suffix = '_inv'
                    new_full_path = tbl_new_path(suffix)

                    try:
                        indexes = intertable['indexes']
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
                    intertables_dict[intertable_id] = {'filename': util.files.filename(new_full_path),
                                                       'method': 'grib_invdist',
                                                       'source_shape': 'NA',
                                                       'target_shape': 'NA',
                                                       'info': 'Converted from v1'}
                    logger.info('Converted and saved to: {}'.format(util.files.filename(new_full_path)))

                elif '_scipy_' in f:
                    try:
                        ixs, w = intertable['indexes'], intertable['coeffs']
                    except IndexError:
                        w, ixs = intertable[0], intertable[1].astype(int, copy=False)

                    for suffix in ('_scipy_nn.npy', '_scipy_invdist.npy'):
                        if f.endswith(suffix):
                            new_full_path = tbl_new_path(suffix)
                            intertable = np.rec.fromarrays((ixs, w), names=('indexes', 'coeffs'))
                            np.save(new_full_path, intertable)
                            intertables_dict[intertable_id] = {'filename': util.files.filename(new_full_path),
                                                               'method': 'nearest',
                                                               'source_shape': 'NA',
                                                               'target_shape': 'NA',
                                                               'info': 'Converted from v1'}
                            logger.info('Converted and saved to: {}'.format(util.files.filename(new_full_path)))

        # update config dict
        self.intertables.dump(intertables_dict)
        logger.detach_config_logger()
