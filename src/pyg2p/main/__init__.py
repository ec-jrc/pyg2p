import logging

from .exceptions import MISSING_CONFIG_FILES, ApplicationException, NO_MESSAGES
from pyg2p.main.config import Configuration
from pyg2p.main.controller import Controller

from pyg2p.main.context import ExecutionContext
from pyg2p.main.exceptions import MISSING_CONFIG_FILES

logging.basicConfig(format='[%(asctime)s][%(name)s] : %(levelname)s %(message)s')
logger = logging.getLogger()


def pyg2p_exe(*args):
    if isinstance(args[0], list):
        args = args[0]
    # read execution configuration (command.json, commandline arguments)
    try:
        # contains main configuration
        # (parameters, geopotentials, intertables, custom user paths, ftp to download test dataset, static data paths)
        conf = Configuration()
        exc_ctx = ExecutionContext(conf, args)
    except ApplicationException as err:
        # error during initalization
        logger.error(f'\nError: {err}\n\n')
        return 1
    except Exception as err:
        logger.error(f'\nError: {err}\n\n')
        return 1

    if exc_ctx.is_config_command:
        try:
            logger.setLevel(logging.ERROR)
            config_command(conf, exc_ctx)
            return 0
        except ApplicationException as err:
            logger.error(f'\nError while running a configuration command: {err}\n\n')
            return 1
    else:
        # normal execution flow
        logger.setLevel(exc_ctx.get('logger.level'))
        ret_value = execute(conf, exc_ctx)
        return ret_value


def execute(conf, exc_ctx):
    ctrl = None
    ret_value = 0
    try:
        if conf.missing_config:
            raise ApplicationException.get_exc(MISSING_CONFIG_FILES, details='{}'.format(','.join(conf.missing_config)))
        ctrl = Controller(exc_ctx)
        ctrl.log_execution_context()
        ctrl.execute()
    except ApplicationException as err:
        logger.error(f'\n\nError: {err}')
        if not err.get_code() == NO_MESSAGES:
            ret_value = 1
    finally:
        ctrl.close()
    return ret_value


def config_command(conf, exc_ctx):
    """Executes one of the commands -W, -K, -g"""
    if exc_ctx.download_conf:  # -W
        # download configuration
        dataset = exc_ctx.get('download_configuration')
        conf.download_data(dataset, logger)
        logger.info('Configuration downloaded.')

    elif exc_ctx.add_geopotential:  # -g
        # add geopotential GRIB file to geopotentials.json and copy it into user configuration folder
        geo = exc_ctx['geopotential']
        conf.add_geopotential(geo)
        logger.info(f'Added geopotential {geo} to configuration')

    elif exc_ctx.check_conf:  # -K
        # check unused intertables (intertables that are not in configuration and can be deleted
        conf.check_conf()
