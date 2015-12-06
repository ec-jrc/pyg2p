import collections

from pyg2p import main
from util.strings import to_argv, to_argdict


def command(*args):
    return Command(*args)


def run_command(cmd):
    argv = to_argv(str(cmd))
    return main(argv[1:])


class Command(object):

    def __init__(self, cmd_string=None):
        self._d = {} if not cmd_string else to_argdict(cmd_string)
        if '-l' not in self._d.keys():
            self._a('-l', 'ERROR')

    def _a(self, opt, param):
        self._d[opt] = param
        return self

    def with_cmdpath(self, param):
        return self._a('-c', param)

    def with_inputfile(self, param):
        return self._a('-i', param)

    def with_ext(self, param):
        return self._a('-x', param)

    def with_log_level(self, param):
        return self._a('-l', param)

    def with_log_dir(self, param):
        return self._a('-d', param)

    def with_eps(self, param):
        return self._a('-m', param)

    def with_tend(self, param):
        return self._a('-e', param)

    def with_tstart(self, param):
        return self._a('-s', param)

    def with_second_input_file(self, param):
        return self._a('-I', param)

    def with_fmap(self, param):
        return self._a('-f', param)

    def with_outdir(self, param):
        return self._a('-o', param)

    def __str__(self):
        cmd = 'pyg2p.py '
        self._d = collections.OrderedDict(sorted(self._d.items(), key=lambda k: k[0]))
        args = ''.join(['%s %s ' % (key, value) for (key, value) in self._d.items()]).strip()
        return cmd + args


