import numexpr as ne
from util.logger import Logger


class Converter:
    def __init__(self, func=None, cut_off=False):

        self._logger = Logger.get_logger()
        self._unitToConvert = None
        self._identity = False
        self._mv = -1

        self._functionString = func
        self._do_cut_off = cut_off

        if self._functionString:
            if self._functionString == 'x=x':
                self._identity = True
            else:
                self._numexpr_eval = 'where(x!=mv, ' + self._functionString.replace('x=', '') + ', mv)'

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def setUnitToConvert(self, unitToConvert):
        self._unitToConvert = unitToConvert

    def setMissingValue(self, mv):
        self._mv = mv

    def mustDoCutOff(self):
        return self._do_cut_off

    def convert(self, x):
        if not self._identity:
            mv = self._mv
            return ne.evaluate(self._numexpr_eval)
        else:
            return x

    def cutOffNegative(self, xs):
        self._log('Cutting off negative values...')
        for k, x in xs.iteritems():
            xs[k] = ne.evaluate("where(x<0, 0, x)")
        return xs

    def __str__(self):
        log_mess = "\nConverting values from units %s. " \
                   "\nFunction: %s" \
                   "\nMissing value: %.2f" % (self._unitToConvert, self._functionString, self._mv)
        return log_mess

