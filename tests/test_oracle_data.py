import pytest

from pyg2p.main import api

from . import logger, check_dataset


@pytest.mark.usefixtures("options")
class TestOracleData:
    @classmethod
    def setup_class(cls):
        # Execute all exemplary pyg2p validated results
        for ds in cls.options['dataset']:
            result_dir = cls.options['results'].joinpath(f'{ds}')
            logger.info(f'\n[!] Removing old test results from {result_dir}')
            for f in result_dir.glob('*'):
                # remove old results
                f.unlink()
            commands_file = cls.options['commands'].joinpath(f'{ds}/commands')
            with open(commands_file) as cfh:
                lines = cfh.readlines()
                for command in lines:
                    command = command.strip()
                    if not command or command.startswith('#'):
                        continue
                    command = f"{command} -N {cls.options['intertables']} -G {cls.options['geopotentials']}"
                    cmd = api.command(command, **cls.options)
                    logger.info(f'\n\n===========> Executing {cmd}')
                    cmd.run()

    def test_dwd(self):
        check_dataset(self, 'dwd')

    def test_eue(self):
        check_dataset(self, 'eue')

    def test_eud(self):
        check_dataset(self, 'eud')

    def test_cosmo(self):
        check_dataset(self, 'cosmo')
