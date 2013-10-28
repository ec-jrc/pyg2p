__author__ = "nappodo"
__date__ = "$Feb 21, 2013 1:52:18 AM$"

from util.logger.Logger import Logger
import numpy as np
import gribpcraster.application.ExecutionContext as ex

class Converter:
    def __init__(self, func=None, cut_off=False):
        import gribpcraster.application.ExecutionContext as ex
        self._logger = Logger('Converter', loggingLevel=ex.global_logger_level)
        self._unitToConvert = None
        self._f = None
        self._identity = False

        self._functionString = func
        self._do_cut_off = cut_off

        if self._functionString:
            if self._functionString=='x=x':
                self._identity = True
            else:
                string_eval = 'lambda ' + self._functionString.replace('=', ',mv:')+ '  if x!=mv else mv'
                self._f = np.vectorize(eval(string_eval))

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def setUnitToConvert(self, unitToConvert):
        self._unitToConvert = unitToConvert

    def setMissingValue(self, mv):
        self._mv = mv

    def mustDoCutOff(self):
        return self._do_cut_off

    def convert(self, x):

        if self._f and not self._identity:
            converted = self._f(x, self._mv)
        else:
            converted = x
        # if self._do_cut_off:
        #     return self.cutOffNegative(converted)
        return converted

    def cutOffNegative(self, xs):
        self._log('Cutting off negative values...')
        for k,x in xs.iteritems():
            x[x < 0] = 0
        return xs

    def __str__(self):
        log_mess = "\nConverting values from units %s. " \
              "\nFunction: %s" \
              "\nMissing value: %.2f"%(self._unitToConvert, self._functionString, self._mv)
        return log_mess

