import inspect
import logging
import os
import gribapi
import sys

import util.files
from main.exceptions import ApplicationException

LOGGERS_REGISTER = {}


class Logger(object):
    _folder = './'
    _level = 'INFO'
    _formatting = '[%(asctime)s] : %(levelname)s %(message)s'
    _logging_level = {'DEBUG': logging.DEBUG, 'ERROR': logging.ERROR, 'WARNING': logging.WARN,
                      'INFO': logging.INFO, 'WARN': logging.WARN, 'CRITICAL': logging.CRITICAL}

    def __init__(self, level, folder):
        self._logger = logging.getLogger('main')
        self._level = self._level if not level else level
        self._folder = self._folder if not folder else folder
        logger_filename = os.path.join(self._folder, 'pyg2p.log')
        logger_dir = os.path.dirname(logger_filename)
        if not util.files.exists(logger_dir):
            util.files.create_dir(logger_dir)
        if not self._logger.handlers:
            hdlr2 = logging.StreamHandler()
            hdlr2.setLevel(self._level)
            hdlr2.setFormatter(logging.Formatter(self._formatting))
            self._logger.addHandler(hdlr2)
        self._logger.propagate = False
        self._logger.setLevel(self._level)

    @property
    def is_debug(self):
        return self._level == 'DEBUG'

    def error(self, message):
        return self.log(message, 'ERROR')

    def info(self, message):
        return self.log(message, 'INFO')

    def debug(self, message):
        return self.log(message)

    def warn(self, message):
        return self.log(message, 'WARNING')

    def warning(self, message):
        return self.log(message, 'WARNING')

    def log(self, message, level='DEBUG'):
        trace_it = 0
        if level == 'ERROR':
            message = '\033[91m' + '\033[1m' + message + '\033[0m'
        message = '{} {}'.format(self._caller_info(), message)
        exc_type, exc_obj, exc_tb = sys.exc_info()
        if isinstance(exc_obj, gribapi.GribInternalError):
            pass
        elif exc_type and not isinstance(exc_obj, ApplicationException):
            print str(exc_obj)
            trace_it = 1
        # elif exc_type and exc_obj.get_code() != 3000:  # no tracestack when no messages exception
        #     trace_it = 1
        self._logger.log(self._get_int_level(level), message, exc_info=trace_it)

    def close(self):
        for i in xrange(len(self._logger.handlers)):
            hdlr = self._logger.handlers.pop()
            hdlr.flush()
            hdlr.close()

    @staticmethod
    def _caller_info():
        try:
            stack = inspect.stack()
            caller = stack[2]
            (callermodulepath, callermodule) = os.path.split(caller[1])
            callerfunction = caller[3]
            callerlinenumber = caller[2]
        except Exception, exc:
            return "[No source information]"
        return "[%(callermodule)s %(callerfunction)s:%(callerlinenumber)d]" % locals()

    def _get_int_level(self, level):
        return self._logging_level.get(level, logging.CRITICAL)

    @classmethod
    def get_logger(cls, level='DEBUG', folder='./logs'):
        if not LOGGERS_REGISTER.get('main'):
            logger = Logger(level, folder)
            LOGGERS_REGISTER['main'] = logger
        return LOGGERS_REGISTER['main']

    @classmethod
    def reset_logger(cls):
        logger = LOGGERS_REGISTER.get('main')
        if logger:
            logger.close()
            del LOGGERS_REGISTER['main']

