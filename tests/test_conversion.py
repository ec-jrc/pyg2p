import numpy as np

from pyg2p.main.manipulation.conversion import Converter


class TestConversion:
    data = np.random.uniform(low=-100.0, high=100.0, size=(100, 100))

    def test_identity(self):
        func = 'x=x'
        converter = Converter(func)
        data = self.data.copy()
        res = converter.convert(data)
        assert np.allclose(data, res)

    def test_conversion(self):
        func = 'x=x-273.15'
        converter = Converter(func)
        data = self.data.copy()
        res = converter.convert(data)
        assert np.allclose(data - 273.15, res)

    def test_cutoff(self):
        assert self.data[self.data < 0].size > 0
        func = 'x=x'
        converter = Converter(func, cut_off=True)
        data = self.data.copy()
        res = converter.convert(data)
        res = converter.cut_off_negative(res)
        assert res[res < 0].size == 0
        assert np.allclose(res[res > 0], data[data > 0])
