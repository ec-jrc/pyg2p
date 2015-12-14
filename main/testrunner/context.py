import json
import os

from util.strings import to_argv


class Test(object):

    def __init__(self, pyg2p_exe, grib2pcraster_exe):
        self.id = ''
        self.out_dir = ''
        self.pyg2p_command = ''
        self.pyg2p_scipy_command = ''
        self.g2p_command = []  # can be two consecutive executions for multiresolution
        self._pyg2p_exe = pyg2p_exe
        self._grib2pcraster_exe = grib2pcraster_exe

    def __str__(self):
        if len(self.g2p_command) > 0:
            self_str = self.id + '\n\t' + self.pyg2p_command + '\n\t' + self._grib2pcraster_exe + ' ' + str(self.g2p_command) + '\n\t- out dir' + self.out_dir
        elif self.pyg2p_scipy_command:
            self_str = self.id + '\n\t' + self.pyg2p_command + '\n\t' +  self.pyg2p_command + ' ' + str(self.pyg2p_scipy_command) + '\n\t- out dir' + self.out_dir
        else:
            self_str = self.id + '\n\t' + self.pyg2p_command + '\n\t- out dir' + self.out_dir
        return self_str


class TestContext(object):

    def __init__(self, json_file):
        json_file = os.path.expanduser(json_file)
        with open(json_file) as f:
            res = json.loads(f.read())
        test_conf = res['TestConfiguration']

        self._params = {'file': json_file, 'pcrasterdiff.exec': test_conf['PcRasterDiff']['@exec'],
                        'atol': float(test_conf['@atol']), 'g2p.exec': test_conf['g2p']['@exec'],
                        'pre_commands': self._get_list_commands(test_conf['@commands']), 'tests': {}}

        for comm in self._params['pre_commands']:
            splitted = comm.split('@')
            map(str.strip, splitted)
            id_ = splitted[0][1:]
            type_ = splitted[0][0]

            args_ = to_argv(splitted[1])
            out_dir_ = './'
            real_args = args_[:]
            for i, val in enumerate(args_):
                if val == '-o':
                    # found output directory argument
                    out_dir_ = args_[i + 1]
                if val == '-n':
                    real_args.remove('-n')
                    real_args.remove(args_[i + 1])
            real_args += ['-n', type_]  # add name prefix
            real_args = ' '.join(real_args)  # back to string
            if id_ in self._params['tests']:
                test_ = self._params['tests'][id_]
            else:
                test_ = Test('pyg2p.py', test_conf['g2p']['@exec'])
                test_.id = id_
                test_.out_dir = out_dir_
                if not test_.out_dir.endswith('/') and not test_.out_dir == '.':
                    test_.out_dir += '/'

                self._params['tests'][id_] = test_

            if type_ == 'g':
                # grib2pcraster command
                test_.g2p_command.append('{} {}'.format(self._params['g2p.exec'], real_args))
            elif type_ == 'p':
                # pyg2p command
                test_.pyg2p_command = real_args
            elif type_ == 'z':
                # pyg2p command (scipy interpolation)
                test_.pyg2p_scipy_command = real_args

    def get(self, param):
        return self._params[param] if param in self._params else None

    @staticmethod
    def _get_list_commands(file_):
        file_ = os.path.expanduser(file_)
        f = open(file_)
        f.seek(0)
        commands = f.readlines()

        def _filter(line):
            return not (line.startswith('#') or line == '' or line == '\n')

        commands = [cmd.strip() for cmd in commands if _filter(cmd.strip())]
        f.close()
        return commands
