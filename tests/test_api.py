import json
import os
import unittest
from main import api
import util.files
from main.config import Configuration
from main.exceptions import ApplicationException


class TestAPI(unittest.TestCase):
    out_1 = '/dataset/testdiffmaps/eueT24'
    cmd_json = '/pyg2p_git/execution_templates_devel/eue_t24.json'
    input_grib_1 = '/dataset/test_2013330702/EpsN320-2013063000.grb'

    @classmethod
    def setUpClass(cls):
        cls.conf = Configuration()

    def setUp(self):

        self._command = api.command()
        args_string = '-l ERROR -c /pyg2p_git/execution_templates_devel/eue_t24.json -i /dataset/test_2013330702/EpsN320-2013063000.grb -o /dataset/testdiffmaps/eueT24 -m 10'
        self._command2 = api.command(args_string)
        self.conf.remove_geopotential('T3999.gph.grb')
        util.files.delete_file(os.path.join(self.conf.geopotentials.data_path, 'T3999.gph.grb'))

    def test_API_init(self):

        self.assertIsInstance(self._command, api.Command)
        command = self._command.with_cmdpath('a.json')
        self.assertDictEqual(command._d, {'-c': 'a.json', '-l': 'ERROR'})
        command.with_inputfile('0.grb')
        self.assertDictEqual(command._d, {'-c': 'a.json', '-i': '0.grb', '-l': 'ERROR'})
        command.with_outdir('/dataout/test').with_tstart('6').with_tend('240').with_eps('10').with_fmap('1').with_ext('4')
        command.with_log_level('ERROR')
        self.assertDictEqual(command._d,
                             {'-c': 'a.json', '-i': '0.grb', '-o': '/dataout/test',
                              '-s': '6', '-e': '240', '-m': '10', '-f': '1', '-x': '4', '-l': 'ERROR'})
        self.assertEqual(str(command), 'pyg2p.py -c a.json -e 240 -f 1 -i 0.grb -l ERROR -m 10 -o /dataout/test -s 6 -x 4')
        self.assertRaises(ApplicationException, api.run_command, *(command,))

    def test_API_run(self):
        self.assertDictEqual(self._command2._d,
                             {'-c': self.cmd_json,
                              '-i': self.input_grib_1,
                              '-o': self.out_1,
                              '-m': '10', '-l': 'ERROR'})

        ret = api.run_command(self._command2)
        self.assertEqual(ret, 0)
        # TODO test other cases for a coverage of 80% of main package
        # scipy interpol, grib interpol, construction of intertables for both,
        # two spatial resolutions, two time resolutions...

    def test_add_geopotential(self):

        u1 = json.load(open(self.conf.geopotentials.config_file))
        g_elem = [x for x in u1['geopotentials']['geopotential'] if x['@name'] == 'T3999.gph.grb']
        self.assertListEqual(g_elem, [])
        self.assertTrue(not util.files.exists(os.path.join(self.conf.geopotentials.data_path, 'T3999.gph.grb')))

        self.conf.add_geopotential('/dataset/maps/fredrik/T3999.gph.grb')

        u1 = json.load(open(self.conf.geopotentials.config_file))
        g_elem = [x for x in u1['geopotentials']['geopotential'] if x['@name'] == 'T3999.gph.grb']
        self.assertEqual(len(g_elem), 1)
        self.assertTrue(util.files.exists(os.path.join(self.conf.geopotentials.data_path, 'T3999.gph.grb')))


