import numpy as np

import pytest

from pyg2p.main import ApplicationException
from pyg2p.main.readers import GRIBReader, PCRasterReader
from pyg2p import GRIBInfo


class TestGribReader:
    def test_read_shortnames(self):
        file = 'tests/data/test.grib'
        reader = GRIBReader(file)
        messages = reader.select_messages(**{'shortName': 'ediff'})
        assert len(messages) == 4
        messages = reader.select_messages(**{'shortName': 'ediff', 'level': 100})
        assert len(messages) == 1

    def test_nomessages(self):
        file = 'tests/data/test.grib'
        reader = GRIBReader(file)
        with pytest.raises(ApplicationException, match="No Messages found - using {'shortName': 'xxx'}"):
            reader.select_messages(**{'shortName': 'xxx'})

    def test_gridid(self):
        file = 'tests/data/test.grib'
        assert GRIBReader.get_id(file, {'shortName': 'ediff'}) == '-71$M$1$1$1$lambert'

    def test_gribinfo(self):
        file = 'tests/data/test.grib'
        reader = GRIBReader(file)
        gribinfo = reader.get_grib_info({'shortName': 'ediff'})
        assert gribinfo == GRIBInfo(input_step=0, input_step2=-1, change_step_at='',
                                    type_of_param='instant', start=0, end=0, mv=9999.0)

    def test_aux(self):
        file = 'tests/data/test.grib'
        reader = GRIBReader(file)
        # get_gids_for_grib_intertable works after call to select_messages
        _ = reader.select_messages(**{'shortName': 'ediff'})
        gid_main_res, val, gid_ext_res, val2 = reader.get_gids_for_grib_intertable()
        assert int(str(gid_main_res)) == gid_main_res
        assert gid_ext_res is None
        assert val2 is None
        assert val == np.array([100.])


class TestPCRasterReader:
    def test_read(self):
        file = 'tests/data/dem.map'
        pcr = PCRasterReader(file)
        assert pcr.min == -9.25
        assert pcr.max == 3539.3720703125
        assert pcr.mv == -3.4028234663852886e+38
