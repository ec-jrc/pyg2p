#!/usr/bin/env python

import sys
from util.logger import Logger
from main.controller import Controller
from main.context import ExecutionContext
from main.config import Configuration
from main import exceptions as appexcmodule

__version__ = '2.0'


def main(*args):
    if __name__ in ("__main__", "pyg2p") and isinstance(args[0], list):
        args = args[0]
    # contains main configuration (parameters, geopotentials, loggers, intertables and geopotentials folders)
    conf = Configuration()
    # read execution configuration (command.json, commandline arguments)
    try:
        exc_ctx = ExecutionContext(conf, args)
    except appexcmodule.ApplicationException, err:
        logger = Logger.get_logger()
        logger.error('\nError: {}\n\n'.format(err))
        logger.close()
        return 1

    logger = Logger.get_logger(exc_ctx.get('logger.level'))
    try:
        executed = config_command(conf, exc_ctx, logger)
        if executed:
            return 0
    except appexcmodule.ApplicationException, err:
        logger.error('\nError while running a configuration command: {}\n\n'.format(err))
        logger.close()
        return 1

    # normal execution flow
    ret_value = execution_command(conf, exc_ctx, logger)
    return ret_value


def execution_command(conf, exc_ctx, logger):
    controller = None
    ret_value = 0
    if not conf.configuration_mode:
        try:
            controller = Controller(exc_ctx)
            controller.log_execution_context()
            controller.execute()
        except appexcmodule.ApplicationException, err:
            logger.error('\n\nError: {}'.format(err))
            if not err.get_code() == appexcmodule.NO_MESSAGES:
                ret_value = 1
        finally:
            controller.close()
            if not exc_ctx.is_a_test:
                logger.close()
    else:
        logger.error(
            '\n\nConfiguration Error: some json files are missing and you need to copy configuration from sources,'
            'or create your own json files before to continue. To copy configuration use option -P')
        ret_value = 1
    return ret_value


def config_command(conf, exc_ctx, logger):
    executed = False
    if exc_ctx.convert_conf:
        # convert old XML configurations to JSON
        Configuration.convert_to_v2(exc_ctx.get('path_to_convert'))
        logger.info('Configuration converted to version 2 in path {}.'.format('path_to_convert'))
        executed = True
    elif exc_ctx.convert_intertables:
        # convert old XML configurations to JSON
        path_to_intertables = exc_ctx.get('path_to_intertables_to_convert')
        conf.convert_intertables_to_v2(path_to_intertables, logger=logger)
        logger.info('Intertables in path {} were updated and copied to {}'.format(path_to_intertables, exc_ctx.configuration.intertables.data_path))
        executed = True
    elif exc_ctx.copy_conf:
        # add geopotential GRIB file to geopotentials.json
        logger.info('Copying default configuration to {}'.format(conf.user.user_conf_dir))
        conf.copy_source_configuration(logger)
        logger.info('Configuration copied.')
        executed = True
    elif exc_ctx.add_geopotential:
        # add geopotential GRIB file to geopotentials.json and copy it into user configuration folder
        conf.add_geopotential(exc_ctx.get('geopotential'))
        logger.info('Added geopotential {} to configuration'.format(exc_ctx.get('geopotential')))
        executed = True
    elif exc_ctx.run_tests:
        # comparison tests between grib2pcraster and pyg2p results
        executed = True
        from main.testrunner import TestRunner
        logger.reset_logger()
        TestRunner(conf.tests.vars, exc_ctx.get('test.cmds')).run()
        logger.close()
    elif exc_ctx.check_conf:
        # comparison tests between grib2pcraster and pyg2p results
        executed = True
        conf.check_conf(logger)
    return executed


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
