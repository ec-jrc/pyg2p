import collections
from functools import partial
from pathlib import Path
from types import MethodType

from pyg2p.main import pyg2p_exe
from pyg2p.util.strings import to_argv, to_argdict


def command(*args, **kwargs):
    return Command(*args, **kwargs)


def run_command(cmd):
    argv = to_argv(str(cmd))
    return pyg2p_exe(argv[1:])


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

    def __init__(self, cmd_string=None, **params):
        cmd_string = cmd_string.lstrip('pyg2p').strip()
        if params:
            opts = params.copy()
            # string interpolation
            for var in opts:
                opts[var] = opts[var].as_posix() if isinstance(opts[var], Path) else str(opts[var])  # as string
                cmd_string = cmd_string.replace('{%s}' % var, opts[var])
        # adding flag underApi
        self._d = {} if not cmd_string else to_argdict(f'{cmd_string} -A')
        # adding log level
        if '-l' not in self._d.keys():
            self._a('-l', 'ERROR')
        # generate API
        for method_suffix, opt in self.cmds_map.items():
            setattr(self, 'with_{}'.format(method_suffix), MethodType(partial(_a, opt), self))

    def __str__(self):
        cmd = 'pyg2p '
        self._d = collections.OrderedDict(sorted(self._d.items(), key=lambda k: k[0]))
        args = ''.join(['%s %s ' % (key, value) for (key, value) in self._d.items()]).strip()
        return cmd + args

    def run(self):
        argv = to_argv(str(self))
        return pyg2p_exe(argv[1:])
