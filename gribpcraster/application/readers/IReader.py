__author__ = 'dominik'

import abc
import gribpcraster.application.ExecutionContext as ex
class IReader(object):

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def close(self):
        """Close the reader and all its resources."""
        return

    @abc.abstractmethod
    def getSelectedMessages(self, **kwargs):
        """Return Values objects according the kwargs selectors."""
        return

    def _log(self, message, level='DEBUG'):
        self._logger.log(message, level)

