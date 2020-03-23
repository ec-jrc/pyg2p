import os

import numpy as np

import pytest

from pyg2p.main.api import Pyg2pApi, ApiContext
from pyg2p.main.readers import PCRasterReader


@pytest.mark.usefixtures("options")
@pytest.mark.oracledata
class TestApi:
    @classmethod
    def setup_class(cls):
        user_conf_dir = os.path.join(os.path.expanduser('~'), '.pyg2p/')
        # set dataroot in user configuration
        if not os.path.exists(user_conf_dir):
            os.mkdir(user_conf_dir)
        with open(os.path.join(user_conf_dir, 'pyg2p_tests.conf'), 'w') as f:
            f.write(f"dataroot={cls.options['dataroot']}")

    def test_parameter_details(self):
        pass

    def test_cosmo_e06(self):
        config = {
            'loggerLevel': 'ERROR',
            'inputFile': self.options['input'].joinpath('cosmo/cos.grb'),
            'fmap': 1,
            'start': 6,
            'end': 132,
            'perturbationNumber': 2,
            'intertableDir': self.options['intertables'].as_posix(),
            'geopotentialDir': self.options['geopotentials'].as_posix(),
            'OutMaps': {
                'unitTime': 24,
                'cloneMap': self.options['maps'].joinpath('dem.map').as_posix(),
                'Interpolation': {
                    "latMap": self.options['maps'].joinpath('lat.map').as_posix(),
                    "lonMap": self.options['maps'].joinpath('lon.map').as_posix(),
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
