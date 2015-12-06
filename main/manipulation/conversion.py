import numexpr as ne
from util.logger import Logger


class Converter:
    def __init__(self, func=None, cut_off=False):

        self._logger = Logger.get_logger()
        self._initial_unit = None
        self._identity = False
        self._mv = -1

        self._function_str = func
        self._do_cut_off = cut_off

        if self._function_str:
            if self._function_str == 'x=x':
                self._identity = True
            else:
                self._numexpr_eval = 'where(x!=mv, ' + self._function_str.replace('x=', '') + ', mv)'

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

    def set_unit_to_convert(self, unit):
        self._initial_unit = unit

    def set_missing_value(self, mv):
        self._mv = mv

    @property
    def must_cut_off(self):
        return self._do_cut_off

    def convert(self, x):
        if not self._identity:
            mv = self._mv
            return ne.evaluate(self._numexpr_eval)
        else:
            return x

    def cut_off_negative(self, xs):
        self._log('Cutting off negative values...')
        for k, x in xs.iteritems():
            xs[k] = ne.evaluate("where(x<0, 0, x)")
        return xs

    def __str__(self):
        log_mess = "\nConverting values from units {}. " \
                   "\nFunction: {}" \
                   "\nMissing value: {.2f}".format(self._initial_unit, self._function_str, self._mv)
        return log_mess

