import os

import numpy as np
from pyg2p.main.config import GeopotentialsConfiguration
from pyg2p.main.interpolation import Interpolator

from pyg2p.main.manipulation.correction import Corrector
from pyg2p.main.readers import GRIBReader, PCRasterReader

from tests import MockedExecutionContext


class TestCorrection:
    def test_correction(self):
        file = 'tests/data/input.grib'
        reader = GRIBReader(file)
        messages = reader.select_messages(shortName='2t')
        grid_id = messages.grid_id
        missing = messages.missing_value
        demmap = PCRasterReader('tests/data/dem.map')
        dem = demmap.values
        dem_mv = demmap.mv
        reader_geopotential = GRIBReader('tests/data/geopotential.grib')
        messages_geopotential = reader_geopotential.select_messages(shortName=GeopotentialsConfiguration.short_names)
        z = messages_geopotential.values_first_or_single_res[messages_geopotential.first_step_range]
        grid_id_geopotential = messages_geopotential.grid_id
        mv_geopotential = messages_geopotential.missing_value
        gem = np.where(z != mv_geopotential, (z / 9.81) * 0.0065, mv_geopotential)
        d = {
            'interpolation.dirs': {'user': os.path.abspath('tests/data/'), 'global': os.path.abspath('tests/data/')},
            'interpolation.lonMap': 'tests/data/lon.map',
            'interpolation.latMap': 'tests/data/lat.map',
            'interpolation.mode': 'nearest',
            'input.file': 'tests/data/input.grib',
            'correction.demMap': 'tests/data/dem.map',
            'correction.formula': 'p+gem-dem*0.0065',
            'correction.gemFormula': '(z/9.81)*0.0065',
        }
        ctx = MockedExecutionContext(d, False)
        corrector = Corrector.get_instance(ctx, grid_id)
        values_in = messages.values_first_or_single_res[messages.first_step_range]
        lats, lons = messages.latlons

        interpolator = Interpolator(ctx, missing)
        values_resampled = interpolator.interpolate_scipy(lats, lons, values_in, grid_id,
                                                          messages.grid_details)
        gem_resampled = interpolator.interpolate_scipy(lats, lons, gem, grid_id_geopotential,
                                                       messages_geopotential.grid_details)
        values_out = corrector.correct(values_resampled)
        # values_resampled + gem_resampled - dem * 0.0065
        reference = np.where((dem != dem_mv) & (values_resampled != dem_mv) & (gem_resampled != dem_mv), values_resampled + gem_resampled - dem * 0.0065, dem_mv)
        assert np.allclose(values_out, reference)
