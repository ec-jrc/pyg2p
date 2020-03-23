from pathlib import Path

import pytest


def pytest_addoption(parser):
    """
    1. Slow tests (interpolation tables creaation) need -X/--runslow to run

    2. Accepting -D/--dataroot option as a path to pyg2p reference data and config.
    E.g.
    pytest -D /workarea/datatest/pyg2p/pyg2p_reference tests/


    Structure of <dataroot> folder must be like:

/datarootpath/
├── commands
│   ├── cosmo
│   │   ├── commands
│   │   ├── cos_e06.json
│   ├── dwd
│   │   ├── commands
│   │   ├── dwdg_c06.json
│   ├── eud
│   │   ├── commands
│   │   ├── eud_e06.json
│   └── eue
│       ├── commands
│       ├── eue_e24.json
├── geopotentials
│   ├── cosmo7km.grb
│   ├── icon_1038240.grb
│   ├── iconeu_720729.grb
│   ├── lsmoro_cy41r2_O1280.grib
│   └── lsmoro_cy41r2_O640.grib
├── input
│   ├── cosmo
│   │   └── cos.grb
│   ├── dwd
│   │   ├── G.grb
│   │   └── L.grb
│   ├── eud
│   │   └── eud.grb
│   └── eue
│       └── eue.grb
├── intertables
│   ├── cos_212065_to_950x1000_nearest.npy
│   ├── icon_1038240_to_950x1000_nearest.npy
│   ├── iconeu_720729_to_950x1000_nearest.npy
│   ├── O1280_6599680_to_950x1000_nearest.npy
│   └── O640_1661440_to_950x1000_nearest.npy
├── maps
│   ├── dem.map
│   ├── lat.map
│   └── lon.map
├── reference
│   ├── cosmo
│   │   ├── E06a0000.001
│   │   ├── E06a0000.002
│   │   ├── E06a0000.003
│   ├── dwd
│   │   ├── C06a0000.001
│   │   ├── C06a0000.002
│   │   ├── C06a0000.003
│   │   ├── C06a0000.004
│   ├── eud
│   │   ├── E06a0000.001
│   │   ├── E06a0000.002
│   │   ├── E06a0000.003
│   └── eue
│       ├── E24a0000.001
│       ├── E24a0000.002
│       ├── E24a0000.003
└── results
    ├── cosmo
    ├── dwd
    ├── eud
    └── eue

    Results of current version tests are placed into respective results/ folders
     and then compared with data from reference folder
    """

    parser.addoption('-D', '--dataroot', type=lambda p: Path(p).absolute(), help='Path to oracle data', required=False)
    parser.addoption('-X', "--runslow", action="store_true", default=False, help="run slow tests")


@pytest.fixture(scope='class', autouse=True)
def options(request):
    options = {'dataroot': request.config.getoption('--dataroot')}
    if options['dataroot']:
        options['commands'] = options['dataroot'].joinpath('commands/')
        options['input'] = options['dataroot'].joinpath('input/')
        options['reference'] = options['dataroot'].joinpath('reference/')
        options['intertables'] = options['dataroot'].joinpath('intertables/')
        options['geopotentials'] = options['dataroot'].joinpath('geopotentials/')
        options['maps'] = options['dataroot'].joinpath('maps/')
        options['results'] = options['dataroot'].joinpath('results/')
        options['dataset'] = ['cosmo', 'dwd', 'eue', 'eud']
    request.cls.options = options


def pytest_configure(config):
    config.addinivalue_line('markers', 'slow: mark test as slow to run')


def pytest_collection_modifyitems(config, items):
    if config.getoption('--runslow') and config.getoption('--dataroot'):
        # --runslow given in cli: do not skip slow tests
        return
    runslow = config.getoption('--runslow')
    test_oracle = config.getoption('--dataroot')
    skip_slow = pytest.mark.skip(reason='need -X/--runslow option to run')
    skip_oracle = pytest.mark.skip(reason='need -D/--dataroot path to run; you should have test oracle accessible as path')
    for item in items:
        if 'slow' in item.keywords and not runslow:
            item.add_marker(skip_slow)
        if 'oracledata' in item.keywords and not test_oracle:
            item.add_marker(skip_oracle)
