SHORTNAME_NOT_FOUND = 1100  # variable not configured in parameters.json
CONVERSION_NOT_FOUND = 1200
INTERTABLE_DIR_NOT_FOUND = 1320
NOT_A_NUMBER = 1400
NO_MESSAGES = 3000  # no messages found in GRIB file with used criteria
NO_GEOPOTENTIAL = 4000  # No geopotential item configured in JSON config
MISSING_FORMULAS_IN_EXEC = 4100
NO_FILE_GEOPOTENTIAL = 4200  # Geopotential file doesn't exist
NO_FILE_DEM = 4300  # DEM pcraster file doesn't exist
NOT_IMPLEMENTED = 6100
NO_VAR_DEFINED = 8000
NO_INTERTABLE_CREATED = 8100
JSON_ERROR = 8200
EXISTING_GEOPOTENTIAL = 8300
INVALID_INTERPOLATION_METHOD = 8400
NO_WRITE_PERMISSIONS = 8500
NO_READ_PERMISSIONS = 8600
NOT_EXISTING_PATH = 8600
MISSING_CONFIG_FILES = 8700
WEIRD_STUFF = 9000
WRONG_ARGS = 10000


class ApplicationException(Exception):

    # TODO: convert key from number to explicative string (e.g. 1000 --> 'file.notfound')
    _errorMessages = {
        0: 'Execution command file not found',
        1000: 'Did not found input file. Check filename.',
        1001: 'Input file not set: use [-i, --inputFile] command line options',
        SHORTNAME_NOT_FOUND: 'shortName not found in parameters.json.',
        CONVERSION_NOT_FOUND: 'shortName - conversionId combination not found in parameters.json.',
        1300: "Latitude or longitude maps doesn't exist. Check filenames in commands json file.",
        1310: 'Clone map doesn''t exist. Check filename in commands xml file.',
        INTERTABLE_DIR_NOT_FOUND: 'Interlookuptables dir must exist. Check name in commands json file or create it.',
        NOT_A_NUMBER: 'Not a number. Check configuration.',
        1500: 'TStart <= TEnd. Check configuration.',
        1600: 'Unkwon interpolation mode.',
        1700: 'Unkwon ext mode. Must be number.',
        2000: 'Found Not Handled parameter value',
        NO_MESSAGES: 'No Messages found',
        NO_GEOPOTENTIAL: 'No geopotential configured in geopotentials.json. Add it with -g option',
        NO_FILE_GEOPOTENTIAL: 'Geopotential configured but file is missing',
        MISSING_FORMULAS_IN_EXEC: 'Both correctionFormula, gemFormula and demMap attributes must be present in the Parameter tag',
        NO_FILE_DEM: 'Did not found demMap file',
        5000: 'Interpolating with not existing lat/lons. Probably a geopotential grib.\n'
              'Geopotentials must be interpolated with an intertable. Try to create it first.',
        6000: 'Trying to interpolate manipulated values \n'
              'with no more reference to original gribs, using grib_api interpolation methods.  \n'
              'Interlookup table must be created, first. Otherwise, use other interpolation methods (nearest or invdist).',
        NOT_IMPLEMENTED: 'Not implemented.',
        7000: 'Commands text file for tests was not found',
        7001: 'Geopotential grib file was not found',
        7002: 'Path to old xml configuration was not found',
        7003: 'Path to grib api intertables was not found',
        NO_VAR_DEFINED: 'Following vars were not found in any of your .conf files. Please add it in ~/.pyg2p/<myconffile>.conf',
        NO_INTERTABLE_CREATED: 'Interpolation table was not found and -B option was not set on command line.',
        JSON_ERROR: 'Error in configuration file.',
        EXISTING_GEOPOTENTIAL: 'Geopotential already existing in configuration with same id',
        INVALID_INTERPOLATION_METHOD: 'Interpolation method not valid',
        WEIRD_STUFF: 'Cannot continue: weird stuff happening',
        NO_WRITE_PERMISSIONS: 'You cannot write to folder',
        NO_READ_PERMISSIONS: 'You cannot read from folder',
        NOT_EXISTING_PATH: 'Not existing paths',
        MISSING_CONFIG_FILES: 'Missing configuration. You may need to run setup.py install again.',
        WRONG_ARGS: 'Failed to parse input arguments.',
    }

    @staticmethod
    def error_description(code):
        if code in ApplicationException._errorMessages:
            return ApplicationException._errorMessages[code]
        else:
            return 'Unknown Error Code: {}'.format(code)

    @classmethod
    def get_exc(cls, code, details=''):
        return cls(None, code, '{} - {}'.format(ApplicationException.error_description(code), str(details)))

    def __init__(self, inner, code, error):
        self._innerException = inner
        self._code = code
        if isinstance(error, basestring):
            self.message = error

    def __str__(self):
        return self.message

    def get_code(self):
        return self._code
