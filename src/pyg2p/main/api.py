import collections
from functools import partial
from types import MethodType

from pyg2p.main import main
from pyg2p.util.strings import to_argv, to_argdict


def command(*args):
    return Command(*args)


def run_command(cmd):
    argv = to_argv(str(cmd))
    return main(argv[1:])


def _a(opt, self, param=''):
    self._d[opt] = param
    return self


class Command(object):
    """
    Class to encapsulate a pyg2p.py command. It uses builder pattern to construct the command.
    Look at the cmds_map dict for available methods to add an argument to command.
    Usage:
    c = Command()
    c = c.with_cmdpath('average.json').with_inputfile('rain.grb').with_outdir('./')
    c = c.with_create_intertable().with_parallel().with_out_format('netcdf')  # boolean args are created without args
    """
    cmds_map = {'cmdpath': '-c', 'inputfile': '-i', 'second_input_file': '-I',
                'eps': '-m', 'tend': '-e', 'tstart': '-s', 'datatime': '-T', 'datadate': '-D',
                'ext': '-x', 'fmap': '-f', 'outdir': '-o', 'nameprefix': '-n',
                'log_level': '-l', 'log_dir': '-d', 'out_format': '-F',
                'create_intertable': '-B', 'parallel': '-X', 'intertable_dir': '-N'}

    def _a(self, opt, param=''):
        self._d[opt] = param
        return self

    def __init__(self, cmd_string=None):
        # adding flag underApi
        self._d = {} if not cmd_string else to_argdict('{} -A'.format(cmd_string))
        if '-l' not in self._d.keys():
            self._a('-l', 'ERROR')
        for method_suffix, opt in self.cmds_map.items():
            setattr(self, 'with_{}'.format(method_suffix), MethodType(partial(_a, opt), self, Command))

    def __str__(self):
        cmd = 'pyg2p '
        self._d = collections.OrderedDict(sorted(self._d.items(), key=lambda k: k[0]))
        args = ''.join(['%s %s ' % (key, value) for (key, value) in self._d.items()]).strip()
        return cmd + args
