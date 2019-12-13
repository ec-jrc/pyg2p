from pathlib import Path

import pytest


def pytest_addoption(parser):
    """
    Accepting -D/--dataroot option as a path to pyg2p reference data and config.
    Structure must be like the following:

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
    options['results'] = options['dataroot'].joinpath('results/')
    options['dataset'] = ['cosmo', 'dwd', 'eue', 'eud']
    request.cls.options = options
