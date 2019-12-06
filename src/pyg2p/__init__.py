import logging

__version__ = '3.0'


class Loggable:

    def __init__(self):
        self._logger = logging.getLogger()

    def _log(self, message, level='DEBUG'):
        self._logger.log(logging._checkLevel(level), message)