#!/usr/bin/env python

import sys

from pyg2p.main import exceptions as appexcmodule
from pyg2p.main.config import Configuration
from pyg2p.main.controller import Controller

from pyg2p.main.context import ExecutionContext
from pyg2p.main.exceptions import MISSING_CONFIG_FILES
from pyg2p.util.logger import Logger

__version__ = '2.0.0'


def main_script():
    # Entry point
    sys.exit(main(sys.argv[1:]))


def main(*args):
    if isinstance(args[0], list):
        args = args[0]
    # read execution configuration (command.json, commandline arguments)
    try:
        # contains main configuration
        # (parameters, geopotentials, intertables, custom user paths, ftp, static data paths)
        conf = Configuration()
        exc_ctx = ExecutionContext(conf, args)
    except appexcmodule.ApplicationException, err:

        logger = Logger.get_logger()
        logger.error('\nError: {}\n\n'.format(err))
        logger.close()
        return 1

    logger = Logger.get_logger(exc_ctx.get('logger.level'))
    if exc_ctx.is_config_command:
        try:
            config_command(conf, exc_ctx, logger)
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
    try:
        if conf.missing_config:
            raise appexcmodule.ApplicationException.get_exc(MISSING_CONFIG_FILES,
                                                            details='{}'.format(','.join(conf.missing_config)))
        controller = Controller(exc_ctx)
        controller.log_execution_context()
        controller.execute()
    except appexcmodule.ApplicationException as err:
        logger.error('\n\nError: {}'.format(err))
        if not err.get_code() == appexcmodule.NO_MESSAGES:
            ret_value = 1
    finally:
        controller.close()
        if not exc_ctx.is_a_test:
            logger.close()
    return ret_value


def config_command(conf, exc_ctx, logger):
    """Executes one of the commands -C, -z, -K, -W, -g, -t"""
    if exc_ctx.convert_conf:  # -C
        # convert old XML configurations to JSON
        Configuration.convert_to_v2(exc_ctx.get('path_to_convert'), logger)
        logger.info('Configuration converted to version 2 in path {}.'.format(exc_ctx.get('path_to_convert')))

    elif exc_ctx.convert_intertables:  # -z
        # convert old XML configurations to JSON
        path_to_intertables = exc_ctx.get('path_to_intertables_to_convert')
        conf.convert_intertables_to_v2(path_to_intertables, logger=logger)
        logger.info('Intertables in path {} were updated and copied to {}'.format(path_to_intertables, exc_ctx.configuration.intertables.data_path))

    elif exc_ctx.download_conf:  # -W
        # add geopotential GRIB file to geopotentials.json
        dataset = exc_ctx.get('download_configuration')
        conf.download_data(dataset, logger)
        logger.info('Configuration downloaded.')

    elif exc_ctx.add_geopotential:  # -g
        # add geopotential GRIB file to geopotentials.json and copy it into user configuration folder
        conf.add_geopotential(exc_ctx.get('geopotential'))
        logger.info('Added geopotential {} to configuration'.format(exc_ctx.get('geopotential')))

    elif exc_ctx.run_tests:  # -t
        # comparison tests (grib2pcraster vs pyg2p, pyg2p scipy interpol vs pyg2p GRIBAPI interpol)
        from pyg2p.main.testrunner import TestRunner
        logger.reset_logger()
        TestRunner(conf.tests.vars, exc_ctx.get('test.cmds')).run()
        logger.close()

    elif exc_ctx.check_conf:  # -K
        # check unused intertables (intertables that are not in configuration and can be deleted
        conf.check_conf(logger)

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
