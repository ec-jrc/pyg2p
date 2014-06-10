__author__ = 'dominik'
import unittest
import pyg2p


class TestAPI(unittest.TestCase):

    def setUp(self):
        self._command = pyg2p.command()
        self._command2 = pyg2p.command('-l ERROR -c /pyg2p_git/execution_templates_devel/eue_t24.xml -i /dataset/test_2013330702/EpsN320-2013063000.grb -o /dataset/testdiffmaps/eueT24 -m 10')

    def test_API_init(self):

        self.assertIsInstance(self._command, pyg2p.Command)
        command = self._command.with_cmdpath('a.xml')
        self.assertDictEqual(command._d, {'-c': 'a.xml'})
        command = command.with_inputfile('0.grb')
        self.assertDictEqual(command._d, {'-c': 'a.xml', '-i': '0.grb'})
        command = command.with_outdir('/dataout/test')
        command = command.with_tstart('6')
        command = command.with_tend('240')
        command = command.with_eps('10')
        command = command.with_fmap('1')
        command = command.with_ext('4')
        command = command.with_log_level('ERROR')
        self.assertDictEqual(command._d,
                             {'-c': 'a.xml', '-i': '0.grb', '-o': '/dataout/test',
                              '-s': '6', '-e': '240', '-m': '10', '-f': '1', '-x': '4', '-l': 'ERROR'})
        self.assertEqual(str(command), 'pyg2p.py -c a.xml -e 240 -f 1 -i 0.grb -l ERROR -m 10 -o /dataout/test -s 6 -x 4')

        ret = pyg2p.run_command(command)
        self.assertEqual(ret, 1)

    def test_API_run(self):
        self.assertDictEqual(self._command2._d,
                             {'-c': '/pyg2p_git/execution_templates_devel/eue_t24.xml',
                              '-i': '/dataset/test_2013330702/EpsN320-2013063000.grb',
                              '-o': '/dataset/testdiffmaps/eueT24',
                              '-m': '10', '-l': 'ERROR'})

        ret = pyg2p.run_command(self._command2)
        self.assertEqual(ret, 0)

    def test_add_geopotential(self):
        #pyg2p.addGeo()
        #TODO
        raise NotImplementedError()


