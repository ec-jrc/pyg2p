__docformat__ = 'restructuredtext'
PYG_P_OUT_LOG = 'pyg2p_out.log'  # file console log
import logging
import inspect
import os,sys
import untangle
from logging import handlers
import util.file.FileManager as FileUtils
from util.generics import FALSE_STRINGS


DIR = './log/'
_logging_level = {'DEBUG': logging.DEBUG, 'ERROR': logging.ERROR,
                  'INFO': logging.INFO, 'WARN': logging.WARN, 'CRITICAL': logging.CRITICAL}
logging.raiseExceptions = False

def _getCallerInfo():
        try:
            stack = inspect.stack()
            caller = stack[2]
            (callerModulePath, callerModule) = os.path.split(caller[1])
            callerFunction = caller[3]
            callerLineNumber = caller[2]
        except Exception, exc:
            return "[No source information]"
        return "[%(callerModule)s %(callerFunction)s:%(callerLineNumber)d]" % locals()

class LoggerItemConfiguration:
    def __init__(self, nameP, formattingP, levelP, fileNameP):
        self.name = nameP
        self.formatting = formattingP
        self.level = levelP
        self.filename = fileNameP


class LoggerConfiguration:
    def __init__(self, configFile):
        self._config_file = configFile
        self._untangled = untangle.parse(configFile)
        self._loggers = {}
        self.file_logging_enabled = True
        if self._untangled.Loggers['enabled'] and self._untangled.Loggers['enabled'] in FALSE_STRINGS:
            self.file_logging_enabled = False

        for loggerItem in self._untangled.Loggers.Logger:
            name = loggerItem['name']
            formatting = loggerItem['formatting']
            level = loggerItem['level']
            fileName = loggerItem['file']
            self._loggers[name] = LoggerItemConfiguration(name, formatting, level, fileName)

    def getLoggerConfiguration(self, name):
        if name in self._loggers:
            return self._loggers[name]
        else:
            sys.stderr.write("[CONSOLE MESSAGE] NO LOGGER CONFIGURATION FOUND FOR " + name)
            sys.stderr.write("[CONSOLE MESSAGE] CHECK " + self._config_file)
            return None

def _getIntLevel(level):
    if level not in ['DEBUG', 'WARN', 'INFO', 'ERROR', 'CRITICAL']:
        return logging.CRITICAL
    return _logging_level[level]


class Logger:
    def __init__(self, name='', configFile="./configuration/logger-configuration.xml", loggingLevel=None):
        dir_ = os.path.dirname(__file__)
        filename = os.path.join(dir_, '../../', configFile)

        self._loggerActivation = True
        self._config = LoggerConfiguration(filename)
        self._logger = None
        self._name = name
        self._loggerLevelConsole = logging.DEBUG

        if name != '':  # not empty name
            self._logger = logging.getLogger(name)
            #configure logger
            logConfigItem = self._config.getLoggerConfiguration(name)
            if logConfigItem and len(self._logger.handlers) == 0:

                import gribpcraster.application.ExecutionContext as execCtx
                logger_level_console = loggingLevel if loggingLevel is not None else logConfigItem.level

                formatting = logConfigItem.formatting
                if self._config.file_logging_enabled:
                    loggerFileName = os.path.join(execCtx.global_out_log_dir, logConfigItem.filename)
                    loggerFileNameConsole = os.path.join(execCtx.global_out_log_dir, PYG_P_OUT_LOG)
                    loggerDir = os.path.dirname(loggerFileName)
                    if self._config.file_logging_enabled and not FileUtils.exists(loggerDir):
                        FileUtils.createDir(loggerDir)
                    hdlr = handlers.TimedRotatingFileHandler(loggerFileName, 'midnight')
                    hdlr.setLevel(logConfigItem.level)
                    hdlr.setFormatter(logging.Formatter(formatting))
                    hdlr3 = handlers.TimedRotatingFileHandler(loggerFileNameConsole, 'midnight')
                    hdlr3.setLevel(logger_level_console)
                    hdlr3.setFormatter(logging.Formatter(formatting))
                    self._logger.addHandler(hdlr)
                    self._logger.addHandler(hdlr3)

                hdlr2 = logging.StreamHandler()
                hdlr2.setLevel(logger_level_console)
                hdlr2.setFormatter(logging.Formatter(formatting))
                self._logger.addHandler(hdlr2)
                self._logger.propagate = False
                self._logger.setLevel(logging.DEBUG)

    def turnOn(self):
        self._loggerActivation = True


    def turnOff(self):
        self._loggerActivation = False


    def log(self, message, level='DEBUG'):
        if self._loggerActivation:
            trace_it = 0
            #if self._logger.name != 'console':
            message = _getCallerInfo() + " " + str(message)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            if exc_type is not None and not hasattr(exc_obj, 'get_code'):
                print str(exc_obj)
                trace_it = 1
            elif exc_type is not None and exc_obj.get_code() != 3000:  #no tracestack when no messages exception
                trace_it = 1
            self._logger.log(_getIntLevel(level), self._logger.name + ' - ' + str(message), exc_info=trace_it)

    def close(self):
        if len(self._logger.handlers) > 0:
            hdlr = self._logger.handlers.pop()
            hdlr.flush()
            hdlr.close()

            self._logger.removeHandler(hdlr)


class NoDebugFilter(logging.Filter):
    def filter(self, record):
        return not record.levelno > logging.DEBUG
