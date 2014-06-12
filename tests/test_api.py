OUT_1 = '/dataset/testdiffmaps/eueT24'
CMD_XML_1 = '/pyg2p_git/execution_templates_devel/eue_t24.xml'
INPUT_GRIB_1 = '/dataset/test_2013330702/EpsN320-2013063000.grb'
__author__ = 'dominik'
import os
import unittest
import untangle
import pyg2p
import util.file.FileManager as fm
from util.configuration import geopotentials as gp


class TestAPI(unittest.TestCase):

    def setUp(self):
        self._command = pyg2p.command()
        args_string = '-l ERROR -c /pyg2p_git/execution_templates_devel/eue_t24.xml -i /dataset/test_2013330702/EpsN320-2013063000.grb -o /dataset/testdiffmaps/eueT24 -m 10'
        self._command2 = pyg2p.command(args_string)
        gp.delete_conf('T3999.gph.grb')
        fm.delete_file(os.path.join(gp.DIR, 'T3999.gph.grb'))

    def test_API_init(self):

        self.assertIsInstance(self._command, pyg2p.Command)
        command = self._command.with_cmdpath('a.xml')
        self.assertDictEqual(command._d, {'-c': 'a.xml', '-l': 'ERROR'})
        command.with_inputfile('0.grb')
        self.assertDictEqual(command._d, {'-c': 'a.xml', '-i': '0.grb', '-l': 'ERROR'})
        command.with_outdir('/dataout/test').with_tstart('6').with_tend('240').with_eps('10').with_fmap('1').with_ext('4')
        command.with_log_level('ERROR')
        self.assertDictEqual(command._d,
                             {'-c': 'a.xml', '-i': '0.grb', '-o': '/dataout/test',
                              '-s': '6', '-e': '240', '-m': '10', '-f': '1', '-x': '4', '-l': 'ERROR'})
        self.assertEqual(str(command), 'pyg2p.py -c a.xml -e 240 -f 1 -i 0.grb -l ERROR -m 10 -o /dataout/test -s 6 -x 4')

        ret = pyg2p.run_command(command)
        self.assertEqual(ret, 1)


    def test_API_run(self):
        self.assertDictEqual(self._command2._d,
                             {'-c': CMD_XML_1,
                              '-i': INPUT_GRIB_1,
                              '-o': OUT_1,
                              '-m': '10', '-l': 'ERROR'})

        ret = pyg2p.run_command(self._command2)
        self.assertEqual(ret, 0)
        # TODO test other cases for a coverage of 80% of gribpcraster package
        # scipy interpol, grib interpol, construction of intertables for both,
        # two spatial resolutions, two time resolutions...

    def test_add_geopotential(self):

        u1 = untangle.parse(gp.CONFIG_FILE)
        g_xml_element = [x for x in u1.geopotentials.geopotential if x['name'] == 'T3999.gph.grb']
        self.assertListEqual(g_xml_element, [])
        self.assertTrue(not fm.exists(os.path.join(gp.DIR, 'T3999.gph.grb')))

        pyg2p.addGeo('/dataset/maps/fredrik/T3999.gph.grb')

        u2 = untangle.parse(gp.CONFIG_FILE)
        g_xml_element = [x for x in u2.geopotentials.geopotential if x['name'] == 'T3999.gph.grb']
        self.assertEqual(len(g_xml_element), 1)
        self.assertTrue(fm.exists(os.path.join(gp.DIR, 'T3999.gph.grb')))


