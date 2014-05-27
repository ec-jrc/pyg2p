#!/usr/bin/env python
import time
import datetime

__author__ = "Nappo Domenico"
__date__ = "$May 25, 2014 15:00$"
__version__ = "1.2.9"

from gribpcraster.exc import ApplicationException as appexcmodule
from gribpcraster.application.ExecutionContext import ExecutionContext
import gribpcraster.application.ExecutionContext as ex
from util.logger.Logger import Logger
from gribpcraster.application.Controller import Controller

import sys


def addGeo(geopotential_file):
    import util.configuration.geopotentials as geo
    geo.add(geopotential_file, _log)


def runTests(test_xml_file):
    from gribpcraster.testrunner.TestRunner import TestRunner
    runner = TestRunner(test_xml_file)
    runner.run()

def main(*args):
    if __name__ == "__main__":
        args = args[0]
    try:
        #read configuration (commands.xml, parameters.xml, loggers, geopotentials.xml if there is correction)
        execCtx = ExecutionContext(args)
        if execCtx.user_wants_help():
            usage()
            return 0
        elif execCtx.user_wants_to_add_geopotential():
            addGeo(execCtx.get('geopotential'))
            return 0
        elif execCtx.user_wants_to_test():
            try:
                import memory_profiler
                runTests(execCtx.get('test.xml'))
                return 0
            except ImportError:
                print 'memory_profiler module is missing'
                print 'try "pip install memory_profile" and re-execute'
                return 0

    except appexcmodule.ApplicationException, err:
        _log('\nError in reading configuration >>>>>>>> {}'.format(str(err)) + '\n\n', 'ERROR')
        ex.global_main_logger.close()
        return 1
    _controller = None
    try:
        _controller = Controller(execCtx)
        _controller.log_execution_context()
        _controller.execute()
    except appexcmodule.ApplicationException, err:
        if err.get_code() == appexcmodule.NO_MESSAGES:
            _log('\n\nError: >>>>>>>>>>>>>>> '+  str(err), 'ERROR')
            return 0
        _log('\n\nError: >>>>>>>>>>>>>>> '+  str(err) + '\n\n', 'ERROR')
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
    print 'Authors: ',  __author__
    print 'Version: ',  __version__
    print 'Date: ',     __date__

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
