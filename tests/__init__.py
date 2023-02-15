import os
import sys
import logging

from lisfloodutilities.compare import Comparator

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, '../src/')
sys.path.append(src_path)

from pyg2p.main import Configuration
from pyg2p.main.readers.pcr import PCRasterReader


logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
logger = logging.getLogger()
logger.propagate = False


def check_dataset_pcroutput(self, ds):
    result_dir = self.options['results'].joinpath(f'{ds}')
    reference_dir = self.options['reference'].joinpath(f'{ds}')
    comparator = Comparator()
    diffs = comparator.compare_dirs(reference_dir.as_posix(), result_dir.as_posix(), skip_missing=False)
    if diffs:
        logger.info(diffs)
    assert not diffs


def check_dataset_netcdfoutput(self, ds):
    result_dir = self.options['results'].joinpath(f'{ds}')
    reference_dir = self.options['reference'].joinpath(f'{ds}')
    mask = PCRasterReader(self.options['maps'].joinpath('dem.map')).values
    comparator = Comparator(mask)
    diffs = comparator.compare_dirs(reference_dir.as_posix(), result_dir.as_posix(), skip_missing=False)
    if diffs:
        logger.info(diffs)
    assert not diffs


config_dict = {
            'interpolation.dirs': {'user': os.path.abspath('tests/data/'), 'global': os.path.abspath('tests/data/')},
            'interpolation.lonMap': 'tests/data/lon.map',
            'interpolation.latMap': 'tests/data/lat.map',
            'interpolation.mode': 'nearest',
            'input.file': 'tests/data/input.grib',
}

api_config_dict = {

}


class MockedExecutionContext:
    conf = Configuration()

    def __init__(self, d, gribinterp=False):
        self._vars = d
        self.is_with_grib_interpolation = gribinterp
        self.configuration = self.conf
        self.configuration.intertables.data_path = os.path.abspath('tests/data/')
        self.configuration.geopotentials.data_path = os.path.abspath('tests/data/')

    def get(self, param, default=None):
        return self._vars.get(param, default)

    def geo_file(self, _):
        return 'tests/data/geopotential.grib'

    def create_select_cmd_for_aggregation_attrs(self):
        return {'shortName': '2t'}
