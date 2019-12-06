from pathlib import Path

import pytest


def pytest_addoption(parser):
    """

    """
    parser.addoption('-D', '--dataroot', type=lambda p: Path(p).absolute(), help='Path to oracle data', required=True)


@pytest.fixture(scope='class', autouse=True)
def options(request):
    options = dict()
    options['dataroot'] = request.config.getoption('--dataroot')
    options['commands'] = options['dataroot'].joinpath('commands/')
    options['input'] = options['dataroot'].joinpath('input/')
    options['reference'] = options['dataroot'].joinpath('reference/')
    options['intertables'] = options['dataroot'].joinpath('intertables/')
    options['geopotentials'] = options['dataroot'].joinpath('geopotentials/')
    options['maps'] = options['dataroot'].joinpath('maps/')
    options['dataset'] = ['cosmo', 'dwd', 'eue', 'eud']
    request.cls.options = options
    return options
