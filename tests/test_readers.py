# TODO
from pyg2p.main.readers import GRIBReader, GRIBInfo, PCRasterReader


class TestGribReader:
    def test_read_shortnames(self):
        file = 'tests/data/test.grib'
        reader = GRIBReader(file)
        messages, short_name = reader.select_messages(**{'shortName': 'ediff'})
        assert len(messages) == 4
        messages, short_name = reader.select_messages(**{'shortName': 'ediff', 'level': 100})
        assert len(messages) == 1


class TestPCRasterReader:
    pass
