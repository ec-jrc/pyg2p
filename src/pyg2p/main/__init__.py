import logging

from ..exceptions import ApplicationException, NO_MESSAGES
from .config import Configuration
from .controller import Controller

from .context import ExecutionContext

logging.basicConfig(format='[%(asctime)s][%(name)s] : %(levelname)s %(message)s')
logger = logging.getLogger()


def pyg2p_exe(*args):
    if isinstance(args[0], list):
        args = args[0]
    # read execution configuration (command.json, commandline arguments)
    try:
        exc_ctx = ExecutionContext(args)
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
            config_command(exc_ctx)
            return 0
        except ApplicationException as err:
            logger.error(f'\nError while running a configuration command: {err}\n\n')
            return 1
    else:
        # normal execution flow
        logger.setLevel(exc_ctx.get('logger.level'))
        ret_value = execute(exc_ctx)
        return ret_value


def execute(exc_ctx):
    ctrl = None
    ret_value = 0
    try:
        ctrl = Controller(exc_ctx)
        ctrl.log_execution_context()
        ctrl.execute()
    except ApplicationException as err:
        logger.error(f'\n\nError: {err}')
        if not err.code == NO_MESSAGES:
            ret_value = 1
    finally:
        ctrl.close()
    return ret_value


def config_command(exc_ctx):
    """Executes one of the commands -W, -K, -g"""
    conf = exc_ctx.configuration
    if exc_ctx.to_download_conf:  # -W
        # download configuration
        dataset = exc_ctx.get('download_configuration')
        conf.download_data(dataset, logger)
        logger.info('Configuration downloaded.')

    elif exc_ctx.to_add_geopotential:  # -g
        # add geopotential GRIB file to geopotentials.json and copy it into user configuration folder
        geo = exc_ctx['geopotential']
        conf.add_geopotential(geo)
        logger.info(f'Added geopotential {geo} to configuration')

    elif exc_ctx.to_check_conf:  # -K
        # check unused intertables (intertables that are not in configuration and can be deleted
        conf.to_check_conf()
