#!/usr/bin/env python

import sys
from util.logger import Logger
from main.Controller import Controller
from main.ExecutionContext import ExecutionContext
from main.config import Configuration
from main import exceptions as appexcmodule

__version__ = 'v2.0'


def main(*args):
    if __name__ in ("__main__", "pyg2p") and isinstance(args[0], list):
        args = args[0]
    # contains main configuration (parameters, geopotentials, loggers, intertables and geopotentials folders)
    conf = Configuration()
    # read execution configuration (command.json, commandline arguments)
    exc_ctx = ExecutionContext(conf, args)
    logger = Logger.get_logger(exc_ctx.get('logger.level'), exc_ctx.get('logger.dir'))
    try:

        if exc_ctx.convert_conf:
            # convert old XML configurations to JSON
            Configuration.convert_to_v2(exc_ctx.get('path_to_convert'))
            return 0
        elif exc_ctx.add_geopotential:
            # add geopotential GRIB file to geopotentials.json
            conf.add_geopotential(exc_ctx.get('geopotential'))
            logger.info('Added geopotential {} to configuration'.format(exc_ctx.get('geopotential')))
            return 0
        elif exc_ctx.run_tests:
            # comparison tests between grib2pcraster and pyg2p results
            try:
                import memory_profiler
                from main.testrunner import TestRunner
                TestRunner(exc_ctx.get('test.json')).run()
                return 0
            except ImportError:
                print 'memory_profiler module is missing'
                print 'try "pip install memory_profiler" and re-execute'
                return 0
    except appexcmodule.ApplicationException, err:
        logger = Logger.get_logger()
        logger.log('\nConfiguration Error: {}'.format(str(err)) + '\n\n', 'ERROR')
        logger.close()
        return 1

    # normal execution flow
    _controller = None

    try:
        _controller = Controller(exc_ctx)
        _controller.log_execution_context()
        _controller.execute()
    except appexcmodule.ApplicationException, err:
        logger.log('\n\nError: {}'.format(str(err)), 'ERROR')
        if err.get_code() == appexcmodule.NO_MESSAGES:
            return 0
        return 1
    finally:
        _controller.close()
        logger.close()
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
