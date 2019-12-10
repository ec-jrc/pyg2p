import pytest

from lisfloodutilities.compare import PCRComparator

from pyg2p.main import api

from . import logger


@pytest.mark.usefixtures("options")
class TestOracleData:
    @classmethod
    def setup_class(cls):
        # Execute all exemplary pyg2p validated results
        for ds in cls.options['dataset']:
            if ds != 'eud':
                continue
            result_dir = cls.options['results'].joinpath(f'{ds}')
            logger.info(f'\n[!] Removing old test results from {result_dir}')
            for f in result_dir.glob('*'):
                # remove old results
                logger.warning(f'Removing {f}')
                f.unlink()
            commands_file = cls.options['commands'].joinpath(f'{ds}/commands')
            with open(commands_file) as cfh:
                lines = cfh.readlines()
                for command in lines:
                    command = command.strip()
                    if not command or command.startswith('#'):
                        continue
                    cmd = api.command(command, **cls.options)
                    logger.info(f'\n\n===========> Executing {cmd}')
                    cmd.run()

    def test_results(self):
        for ds in self.options['dataset']:
            if ds != 'eud':
                continue
            result_dir = self.options['results'].joinpath(f'{ds}')
            reference_dir = self.options['reference'].joinpath(f'{ds}')
            comparator = PCRComparator()
            diffs = comparator.compare_dirs(reference_dir.as_posix(), result_dir.as_posix())
            assert not diffs
