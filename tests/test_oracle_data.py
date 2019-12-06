import pytest

from pyg2p.main import api


@pytest.mark.usefixtures("options")
class TestOracleData:
    @classmethod
    def setup_class(cls):
        for ds in cls.options['dataset']:
            commands_file = cls.options['dataroot'].joinpath(f'commands/{ds}/commands')
            with open(commands_file) as cfh:
                lines = cfh.readlines()
                for command in lines:
                    cmd = api.command(command)
                    cmd.run()
