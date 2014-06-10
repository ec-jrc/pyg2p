NO_MESSAGES = 3000


class ApplicationException(Exception):

    #TODO: convert key from number to explicative string (e.g. 1000 --> 'file.notfound')
    _errorMessages = {
        0: 'Execution command file not found',
        1000: 'Did not found input file. Check filename.',
        1001: 'Input file not set as -i or --inputFile command line option',
        1100: 'shortName not found in parameters.xml.',
        1200: 'shortName - conversionId combination not found in parameters.xml.',
        1300: 'Latitude or longitude maps doesn''t exist. Check filenames in commands xml file.',
        1310: 'Clone map doesn''t exist. Check filename in commands xml file.',
        1320: 'Interlookuptables dir must exist. Check name in commands xml file or create it.',
        1400: 'Not a number. Check configuration.',
        1500: 'TStart<=TEnd. Check configuration.',
        1600: 'Unkwon interpolation mode.',
        1700: 'Unkwon ext mode. Must be number.',
        2000: 'Found Not Handled parameter value',
        NO_MESSAGES: 'No Messages found',
        4000: 'No geopotential filename found in geopotentials.xml (for correction)',
        4100: 'Both correctionFormula, gemFormula and demMap attributes must be present in the Parameter tag',
        4200: 'Did not found demMap file',
        5000: 'Interpolating with not existing lat/lons. Probably a geopotential grib.\n'
              'Geopotentials must be interpolated with an intertable. Try to create it first.',
        6000: 'Trying to interpolate manipulated values \n'
              'with no more reference to original gribs, using grib_api interpolation methods.  \n'
              'Interlookup table must be created, first. Otherwise, use other interpolation methods (nearest or invdist).',
        6100: 'Manipulation not implemented.',
        7000: 'XML configuration file for tests was not found',
        7001: 'Geopotential grib file was not found'
    }

    @staticmethod
    def _getErrorDescription(code):
        if code in ApplicationException._errorMessages:
            return ApplicationException._errorMessages[code]
        else:
            return 'Unknown Error Code: '+code

    @classmethod
    def get_programmatic_exc(cls, code, details=''):
        return cls(None, code, ApplicationException._getErrorDescription(code) + ' ' + str(details))

    def __init__(self, inner, code, error):
        self.__innerException = inner
        self._code = code
        if type(error).__name__ == 'str':
            self.message = 'Application Error: ' + error

    def __str__(self):
        return self.message

    def get_code(self):
        return self._code
