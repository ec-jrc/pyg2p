#!/usr/bin/env python

import sys
from util.logger import Logger
from main.Controller import Controller
from main.ExecutionContext import ExecutionContext
from main.config import Configuration
from main import exceptions as appexcmodule

__version__ = 'v2.0'


def run_tests(test_xml_file):
    from main.testrunner.TestRunner import TestRunner
    runner = TestRunner(test_xml_file)
    runner.run()


def main(*args):
    if __name__ in ("__main__", "pyg2p") and isinstance(args[0], list):
        args = args[0]
    # contains main configuration (parameters, geopotentials, loggers, intertables and geopotentials folders)
    conf = Configuration()
    # read execution configuration (command.json, commandline arguments)
    exc_ctx = ExecutionContext(conf, args)

    try:

        if exc_ctx.convert_conf:
            Configuration.convert_to_v2(exc_ctx.get('path_to_convert'))
            return 0
        elif exc_ctx.add_geopotential:
            conf.add_geopotential(exc_ctx.get('geopotential'))
            return 0
        elif exc_ctx.run_tests:
            import memory_profiler
            try:
                run_tests(exc_ctx.get('test.json'))
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

    _controller = None
    logger = Logger.get_logger(exc_ctx.get('logger.level'), exc_ctx.get('logger.dir'))
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
