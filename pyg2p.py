#!/usr/bin/env python

__author__ = "Nappo Domenico"
__date__ = "November 15, 2014 19:00"
__version__ = "1.3.2"

import sys
import collections
from gribpcraster.exc import ApplicationException as appexcmodule
from gribpcraster.application.ExecutionContext import ExecutionContext
import gribpcraster.application.ExecutionContext as ex
from gribpcraster.application.Controller import Controller
from util.conversion.FromStringConversion import to_argv, to_argdict


# API

#Command factory
def command(*args):
    return Command(*args)


def run_command(cmd):
    argv = to_argv(str(cmd))
    return main(argv[1:])


def add_geo(geopotential_file):
    import util.configuration.geopotentials as geo
    geo.add(geopotential_file, _log)


def run_tests(test_xml_file):
    from gribpcraster.testrunner.TestRunner import TestRunner
    runner = TestRunner(test_xml_file)
    runner.run()


class Command(object):

    def __init__(self, cmd_string=None):
        self._d = {} if not cmd_string else to_argdict(cmd_string)
        if not '-l' in self._d.keys():
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


# END API

def main(*args):
    if __name__ in ("__main__", "pyg2p") and isinstance(args[0], list):
        args = args[0]
    try:
        #read configuration (commands.xml, parameters.xml, loggers, geopotentials.xml if there is correction)
        exc_ctx = ExecutionContext(args)

        if exc_ctx.user_wants_help():
            usage()
            return 0
        elif exc_ctx.user_wants_to_add_geopotential():
            add_geo(exc_ctx.get('geopotential'))
            return 0
        elif exc_ctx.user_wants_to_test():
            import memory_profiler
            try:
                run_tests(exc_ctx.get('test.xml'))
                return 0
            except ImportError:
                print 'memory_profiler module is missing'
                print 'try "pip install memory_profiler" and re-execute'
                return 0

    except appexcmodule.ApplicationException, err:
        _log('\nConfiguration Error: {}'.format(str(err)) + '\n\n', 'ERROR')
        ex.global_main_logger.close()
        return 1

    _controller = None
    try:
        _controller = Controller(exc_ctx)
        _controller.log_execution_context()
        _controller.execute()
    except appexcmodule.ApplicationException, err:
        _log('\n\nError: {}'.format(str(err)), 'ERROR')
        if err.get_code() == appexcmodule.NO_MESSAGES:
            return 0
        return 1
    finally:
        _controller.close()
        ex.global_main_logger.close()
    return 0


def _log(message, level='DEBUG'):
    ex.global_main_logger.log(message, level)


def usage():
    # prints some lines describing how to use this program
    # accepted input arguments, etc

    print '\n\npyg2p - a program to convert from GRIB (1 & 2) to PCRaster \n'
    print 'Authors: {}'.format(__author__)
    print 'Version: {}'.format(__version__)
    print 'Date: {}'.format(__date__)

    print """
    Execute the grib to pcraster conversion using parameters from the input xml configuration
    Read user and configuration manuals

    Example usage:
        ./pyg2p.py -c </path/to/xml/template> -i </path/to/grib/file> [-I </path/to/grib/2ndres/file>]| [-s <tstart>] [-e <tend>] -o </path/to/out/dir> [-l <DEBUG|INFO|ERROR>] [-d </path/to/logs>]
        ./pyg2p.py --commandsFile=</path/to/xml/template> --inputFile=</path/to/grib/file> [--start <tstart>] [--end <tend>] [--inputFile2=</path/to/grib/2ndres/file>] --outDir==</path/to/logs>
        ./pyg2p.py -g </path/to/geopotential/grib/file>
        ./pyg2p.py -t </path/to/test/xml_conf>
        ./pyg2p.py -h

    -c, --commandsFile </path/to/input/xml>

    -i --inputFile </path/to/input/grib>
         Grib source file

    -I --inputFile2 </path/to/input/grib/2ndres/file>
         (optional)
         Grib source file with 2nd resolution messages

    -s --start <tstart>
        grib timestep start. It overwrites the tstart in xml execution file.

    -e --end <tend>
        grib timestep end. It overwrites the tend in xml execution file.

    -m --perturbationNumber: <eps member number>
         (ex: -m 10)

    -o --outDir output maps dir
         (optional, default: ./)

    -f --fmap first map number
         (optional, default: 1)

    -x --ext extension number step
        (optional, default: 1)

    -l --loggerLevel: <console logging level>
         (optional, default: level of CONSOLE logger as configured in logger-configuration.xml)
         Use DEBUG if you want a lot of text on terminal!!!
         (ex: -l INFO)

    -d --outLogDir output logs dir
         (optional, default: ./logs)

    -g --addGeopotential </path/to/geopotential/grib/file>
         Add the file to geopotentials.xml configuration file, to use for correction.
         The file will be copied into the right folder (configuration/geopotentials)
         Note: shortName of geopotential must be 'fis' or 'z'

    -t --test </path/to/test/xml_conf>
        version 1.05: will execute a battery of commands defined in configuration/tests/pyg2p_commands.txt
        version 1.1: will execute a battery of commands defined in configuration/tests/pyg2p_commands.txt
            and in configuration/tests/g2p_commands.txt. Then it will create diff pcraster maps and log alerts
            if differences are higher than a threshold
    -h --help
         Display this help message
    """

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

