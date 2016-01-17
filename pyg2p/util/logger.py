import inspect
import logging
import os
import sys

import gribapi

from pyg2p.main.exceptions import ApplicationException
from pyg2p.util.generics import FAIL, YELLOW, ENDC

LOGGERS_REGISTER = {}


class Logger(object):
    _level = 'INFO'
    _formatting = '[%(asctime)s] : %(levelname)s %(message)s'
    _logging_level = {'DEBUG': logging.DEBUG, 'ERROR': logging.ERROR, 'WARNING': logging.WARN,
                      'INFO': logging.INFO, 'WARN': logging.WARN, 'CRITICAL': logging.CRITICAL}

    def __init__(self, level):
        self._logger = logging.getLogger('main')
        self._level = self._level if not level else level
        if not self._logger.handlers:
            # TODO add file handlers and add an option to argparse to log to folder/file
            hdlr = logging.StreamHandler()
            hdlr.setLevel(self._level)
            hdlr.setFormatter(logging.Formatter(self._formatting))
            self._logger.addHandler(hdlr)
        self._logger.propagate = False
        self._logger.setLevel(self._level)
        self._temp_handlers = None
        self._ch = None  # config handler

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
        color = FAIL if level == 'ERROR' else YELLOW
        if level in ('ERROR', 'WARN', 'WARNING'):
            message = '{}{}{}'.format(color, message, ENDC)
        message = '{} {}'.format(self._caller_info(), message)
        exc_type, exc_obj, exc_tb = sys.exc_info()
        if level == 'DEBUG':
            if isinstance(exc_obj, gribapi.GribInternalError):
                pass
            elif exc_type and not isinstance(exc_obj, ApplicationException):
                print str(exc_obj)
                trace_it = 1
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
    def get_logger(cls, level='DEBUG'):
        if not LOGGERS_REGISTER.get('main'):
            logger = Logger(level)
            LOGGERS_REGISTER['main'] = logger
        return LOGGERS_REGISTER['main']

    @classmethod
    def reset_logger(cls):
        logger = LOGGERS_REGISTER.get('main')
        if logger:
            logger.close()
            del LOGGERS_REGISTER['main']

    def attach_config_logger(self):
        self._temp_handlers = self._logger.handlers
        # detach console handler
        self._logger.handlers = []
        self._ch = logging.StreamHandler()
        self._ch.setLevel(logging.INFO)
        # create formatter and add it to the handlers
        formatter = logging.Formatter('%(message)s')
        self._ch.setFormatter(formatter)
        self._logger.addHandler(self._ch)

    def detach_config_logger(self):
        self._logger.removeHandler(self._ch)
        self._logger.handlers = self._temp_handlers

