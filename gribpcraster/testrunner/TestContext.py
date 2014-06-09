__author__ = 'dominik'
import untangle as unt
from util.conversion.FromStringConversion import to_argv
from util.file.FileManager import FileManager


def _filter(cmd):
    return not (cmd.startswith('#') or cmd == '' or cmd == '\n')


def _get_list_commands(file_):
    f = FileManager(file_)
    commands = f.readFile()
    commands = [cmd.strip() for cmd in commands if _filter(cmd.strip())]
    f.close()
    return commands


class Test(object):

    def __init__(self):
        self.id = ''
        self.out_dir = ''
        self.pyg2p_command = ''
        self.pyg2p_scipy_command = ''
        self.g2p_command = []  # can be two consecutive executions for multiresolution

    def __str__(self):
        if len(self.g2p_command)>0:

            self_str = self.id + '\n\t- pyg2p comm' + self.pyg2p_command + '\n\t- g2p comms ' + str(self.g2p_command) + '\n\t- out dir' + self.out_dir
        elif self.pyg2p_scipy_command:
            self_str = self.id + '\n\t- pyg2p comm' + self.pyg2p_command + '\n\t- pyg2p scipy interpol ' + str(self.pyg2p_scipy_command) + '\n\t- out dir' + self.out_dir
        else:
            self_str = self.id + '\n\t- pyg2p comm' + self.pyg2p_command + '\n\t- out dir' + self.out_dir
        return self_str

class TestContext(object):

    def __init__(self, xmlfile):
        xmltest = unt.parse(xmlfile)
        xml_conf = xmltest.TestConfiguration

        self._params = {'file': xmlfile, 'pcrasterdiff.exec': xml_conf.PcRasterDiff['exec'],
                        'atol': float(xml_conf['atol']), 'g2p.exec': xml_conf.g2p['exec'],
                        'pre_commands': _get_list_commands(xml_conf['commands']), 'tests': {}}
        for comm in self._params['pre_commands']:
            splitted = comm.split('@')
            map(str.strip, splitted)
            id_ = splitted[0][1:]
            type_ = splitted[0][0]
            args_ = to_argv(splitted[1])
            out_dir_ = './'
            for i in range(len(args_)):
                if args_[i] == '-o':
                    #found output directory argument
                    out_dir_ = args_[i + 1]
                    break

            if id_ in self._params['tests']:
                test_ = self._params['tests'][id_]
            else:
                test_ = Test()
                test_.id = id_
                test_.out_dir = out_dir_
                if not test_.out_dir.endswith('/') and not test_.out_dir == '.':
                    test_.out_dir += '/'

                self._params['tests'][id_] = test_

            if type_ == 'g':
                # grib2pcraster command
                test_.g2p_command.append(self._params['g2p.exec'] + ' ' + splitted[1])
            elif type_ == 'p':
                # pyg2p command
                test_.pyg2p_command = splitted[1]
            elif type_ == 'z':
                # pyg2p command
                test_.pyg2p_scipy_command = splitted[1]

    def get(self, param):
        return self._params[param] if param in self._params else None
