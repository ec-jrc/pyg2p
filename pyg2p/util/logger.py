import inspect
import logging
import os
import sys

import gribapi

from pyg2p.util.generics import FAIL, YELLOW, ENDC

LOGGERS_REGISTER = {}


class Logger(object):
    level = 'INFO'  # default level
    _formatting = '[%(asctime)s] : %(levelname)s %(message)s'
    _logging_level = {'DEBUG': logging.DEBUG, 'ERROR': logging.ERROR, 'WARNING': logging.WARN,
                      'INFO': logging.INFO, 'WARN': logging.WARN, 'CRITICAL': logging.CRITICAL}

    def __init__(self, level):
        self._logger = logging.getLogger('main')
        self.level = self.level if not level else level
        if not self._logger.handlers:
            # TODO add file handlers and add an option to argparse to log to folder/file
            hdlr = logging.StreamHandler()
            hdlr.setLevel(self.level)
            hdlr.setFormatter(logging.Formatter(self._formatting))
            self._logger.addHandler(hdlr)
        self._logger.propagate = False
        self._logger.setLevel(self.level)
        self._temp_handlers = None
        self._ch = None  # config handler

    @property
    def is_debug(self):
        return self.level == 'DEBUG'

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
        if level in ('ERROR', 'WARN', 'WARNING'):
            color = FAIL if level == 'ERROR' else YELLOW
            message = '{}{}{}'.format(color, message, ENDC)
        message = '{} {}'.format(self._caller_info(), message)
        if self.is_debug:
            # add traceback only at debug
            exc_type, exc_obj, exc_tb = sys.exc_info()
            if not isinstance(exc_obj, gribapi.GribInternalError) and exc_type:
                print str(exc_obj)
                trace_it = 1
        self._logger.log(self._get_int_level(level), message, exc_info=trace_it)

    def flush(self):
        for hdlr in self._logger.handlers:
            hdlr.flush()
            # hdlr.close()

    @staticmethod
    def _caller_info():
        try:
            stack = inspect.stack()
            caller = stack[3]
            (callermodulepath, callermodule) = os.path.split(caller[1])
            callerfunction = caller[3]
            callerlinenumber = caller[2]
        except Exception as exc:
            return '[No source information]'
        return '[{callermodule:s} {callerfunction:s}:{callerlinenumber:d}]'.format(**locals())

    def _get_int_level(self, level):
        return self._logging_level.get(level, logging.CRITICAL)

    @classmethod
    def get_logger(cls, level='DEBUG', name='main'):
        logger = LOGGERS_REGISTER.get(name)
        if not logger:
            logger = Logger(level)
            LOGGERS_REGISTER[name] = logger
        return logger

    @classmethod
    def reset_logger(cls):
        logger = LOGGERS_REGISTER.get('main')
        if logger:
            logger.flush()
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

