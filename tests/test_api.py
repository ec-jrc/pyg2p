import os
from copy import deepcopy

import numpy as np

import pytest

from pyg2p.main.api import Pyg2pApi, ApiContext
from pyg2p.main.readers import PCRasterReader


@pytest.mark.usefixtures("options")
@pytest.mark.oracledata
class TestApi:
    input_path = None
    intertables_path = None
    geopotentials_path = None
    dem_map = None
    lat_map = None
    lon_map = None

    config = {
        'loggerLevel': 'ERROR',
        'inputFile': '',
        'fmap': 1,
        'start': 6,
        'end': 132,
        'perturbationNumber': 2,
        'intertableDir': '',
        'geopotentialDir': '',
        'OutMaps': {
            'unitTime': 24,
            'cloneMap': '',
            'Interpolation': {
                "latMap": '',
                "lonMap": '',
                "mode": "nearest"
            }
        },

        'Aggregation': {
            'step': 6,
            'type': 'average'
        },
        'Parameter': {
            'shortName': 'alhfl_s',
            'applyConversion': 'tommd',
        },
    }

    @classmethod
    def setup_class(cls):
        user_conf_dir = os.path.join(os.path.expanduser('~'), '.pyg2p/')
        # set dataroot in user configuration
        if not os.path.exists(user_conf_dir):
            os.mkdir(user_conf_dir)
        with open(os.path.join(user_conf_dir, 'pyg2p_tests.conf'), 'w') as f:
            f.write(f"dataroot={cls.options['dataroot']}")
        cls.input_path = cls.options['input']
        cls.intertables_path = cls.options['intertables']
        cls.geopotentials_path = cls.options['geopotentials']
        cls.dem_map = cls.options['maps'].joinpath('dem.map').as_posix()
        cls.lat_map = cls.options['maps'].joinpath('lat.map').as_posix()
        cls.lon_map = cls.options['maps'].joinpath('lon.map').as_posix()
        cls.config['intertableDir'] = cls.intertables_path
        cls.config['geopotentialDir'] = cls.geopotentials_path
        cls.config['OutMaps']['cloneMap'] = cls.dem_map
        cls.config['OutMaps']['Interpolation']['latMap'] = cls.lat_map
        cls.config['OutMaps']['Interpolation']['lonMap'] = cls.lon_map

    def test_parameter_details(self):
        t = Pyg2pApi.parameter_details('2t')
        assert isinstance(t, str)
        assert 'Parameter 2t: 2 meters Temperature Unit: K' in t
        assert 'Conversion id: k2c unit C x=x-273.15 [cut negative: False]' in t
        t = Pyg2pApi.parameter_details()
        assert '2t' in t

    def test_cosmo_e06(self):
        config = deepcopy(self.config)
        config['inputFile'] = self.input_path.joinpath('cosmo/cos.grb')

        ctx = ApiContext(config)
        api = Pyg2pApi(ctx)
        assert not api.values
        assert not api.messages
        out_values = api.execute()
        assert api.values
        assert api.messages  # original GRIB messages and information class pyg2p.Messages
        assert len(out_values) == 22

        for i, (step, val) in enumerate(out_values.items(), start=1):
            i = str(i).zfill(3)
            reference = PCRasterReader(self.options['reference'].joinpath(f'cosmo/E06a0000.{i}')).values
            diff = np.abs(reference - val)
            assert np.allclose(diff, np.zeros(diff.shape), rtol=1.e-2, atol=1.e-3, equal_nan=True)

    def test_cosmo_r06(self):
        config = deepcopy(self.config)
        config['inputFile'] = self.input_path.joinpath('cosmo/cos.grb')
        config['Aggregation']['type'] = 'accumulation'
        config['Aggregation']['forceZeroArray'] = 'y'
        config['Parameter']['shortName'] = 'tp'
        config['Parameter']['applyConversion'] = 'cut'

        ctx = ApiContext(config)
        api = Pyg2pApi(ctx)
        out_values = api.execute()
        assert len(out_values) == 22

        for i, (step, val) in enumerate(out_values.items(), start=1):
            i = str(i).zfill(3)
            reference = PCRasterReader(self.options['reference'].joinpath(f'cosmo/R06a0000.{i}')).values
            diff = np.abs(reference - val)
            assert np.allclose(diff, np.zeros(diff.shape), rtol=1.e-2, atol=1.e-3, equal_nan=True)

    def test_cosmo_t24(self):
        config = deepcopy(self.config)
        config['inputFile'] = self.input_path.joinpath('cosmo/cos.grb')
        config['ext'] = 1
        config['start'] = 24

        config['Aggregation']['type'] = 'average'
        config['Aggregation']['step'] = 24
        config['Parameter']['shortName'] = '2t'
        config['Parameter']['applyConversion'] = 'k2c'
        config['Parameter']['demMap'] = self.dem_map
        config['Parameter']['gem'] = '(z/9.81)*0.0065'
        config['Parameter']['correctionFormula'] = 'p+gem-dem*0.0065'

        ctx = ApiContext(config)
        api = Pyg2pApi(ctx)
        out_values = api.execute()
        assert len(out_values) == 5

        i = 1
        for step, val in out_values.items():
            i = str(i).zfill(3)
            reference = PCRasterReader(self.options['reference'].joinpath(f'cosmo/T24a0000.{i}')).values
            diff = np.abs(reference - val)
            assert np.allclose(diff, np.zeros(diff.shape), rtol=1.e-2, atol=1.e-3, equal_nan=True)
            i = int(i)
            i += 4

    def test_iconeut24(self):
        config = deepcopy(self.config)
        config['inputFile'] = self.input_path.joinpath('dwd/L.grb')
        config['start'] = 1440
        config['end'] = 7200
        config['ext'] = 4
        config['perturbationNumber'] = None
        config['Aggregation']['type'] = 'average'
        config['Aggregation']['step'] = 1440
        config['Parameter']['shortName'] = '2t'
        config['Parameter']['applyConversion'] = 'k2c'
        config['Parameter']['demMap'] = self.dem_map
        config['Parameter']['gem'] = '(z/9.81)*0.0065'
        config['Parameter']['correctionFormula'] = 'p+gem-dem*0.0065'
        ctx = ApiContext(config)
        api = Pyg2pApi(ctx)
        out_values = api.execute()
        assert len(out_values) == 5

        i = 1
        for step, val in out_values.items():
            i = str(i).zfill(3)
            reference = PCRasterReader(self.options['reference'].joinpath(f'dwd/T24a0000.{i}')).values
            diff = np.abs(reference - val)
            assert np.allclose(diff, np.zeros(diff.shape), rtol=1.e-2, atol=1.e-3, equal_nan=True)
            i = int(i)
            i += 4

    def test_dwdt24(self):
        config = deepcopy(self.config)
        config['inputFile'] = self.input_path.joinpath('dwd/G.grb')
        config['start'] = 8640
        config['end'] = 10080
        config['ext'] = 4
        config['fmap'] = 21
        config['perturbationNumber'] = None
        config['Aggregation']['type'] = 'average'
        config['Aggregation']['step'] = 1440
        config['Parameter']['shortName'] = '2t'
        config['Parameter']['applyConversion'] = 'k2c'
        config['Parameter']['demMap'] = self.dem_map
        config['Parameter']['gem'] = '(z/9.81)*0.0065'
        config['Parameter']['correctionFormula'] = 'p+gem-dem*0.0065'
        ctx = ApiContext(config)
        api = Pyg2pApi(ctx)
        out_values = api.execute()
        assert len(out_values) == 2

        i = 21
        for step, val in out_values.items():
            i = str(i).zfill(3)
            reference = PCRasterReader(self.options['reference'].joinpath(f'dwd/T24a0000.{i}')).values
            diff = np.abs(reference - val)
            assert np.allclose(diff, np.zeros(diff.shape), rtol=1.e-2, atol=1.e-3, equal_nan=True)
            i = int(i)
            i += 4

    @pytest.mark.slow
    def test_createintertable(self):
        config = deepcopy(self.config)
        config['inputFile'] = 'tests/data/input.grib'
        config['intertableDir'] = 'tests/data'
        config['createIntertable'] = True
        config['interpolationParallel'] = True
        config['OutMaps']['Interpolation']['mode'] = 'invdist'
        config['OutMaps']['Interpolation']['latMap'] = 'tests/data/lat.map'
        config['OutMaps']['Interpolation']['lonMap'] = 'tests/data/lon.map'
        config['OutMaps']['cloneMap'] = 'tests/data/dem.map'
        config['perturbationNumber'] = None
        config['Aggregation'] = None
        config['Parameter']['shortName'] = '2t'
        config['Parameter']['applyConversion'] = 'k2c'
        config['Parameter']['demMap'] = 'tests/data/dem.map'
        config['Parameter']['gem'] = '(z/9.81)*0.0065'
        config['Parameter']['correctionFormula'] = 'p+gem-dem*0.0065'
        ctx = ApiContext(config)
        api = Pyg2pApi(ctx)
        out_values = api.execute()
        shape_target = PCRasterReader(config['OutMaps']['Interpolation']['latMap']).values.shape
        assert shape_target == list(out_values.values())[0].shape
        os.unlink('tests/data/tbl_pf10tp_550800_scipy_invdist.npy.gz')
