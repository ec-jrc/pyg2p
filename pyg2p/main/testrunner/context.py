import os

from pyg2p.util.strings import to_argv


class Test(object):
    _pyg2p_exe = 'pyg2p.py'

    def __init__(self):
        self.id = ''
        self.out_dir = ''
        self.pyg2p_command = ''
        self.pyg2p_scipy_command = ''
        self.g2p_command = []  # can be two consecutive executions for multiresolution

    def __str__(self):
        if self.pyg2p_scipy_command:
            res = '{}\n\t{} {}\n\t{} {}'.format(self.id, self._pyg2p_exe, self.pyg2p_command, self._pyg2p_exe, self.pyg2p_scipy_command)
        else:
            res = '{}\n\t{} {}\n\t{}'.format(self.id, self._pyg2p_exe, self.pyg2p_command, ' '.join(self.g2p_command))
        return res


class TestContext(object):

    def __init__(self, config, cmds_file):
        test_conf = config['TestConfiguration']

        self._params = {'pcrasterdiff.exec': test_conf['PcRasterDiff']['@exec'],
                        'atol': float(test_conf['@atol']), 'g2p.exec': test_conf['g2p']['@exec'],
                        'pre_commands': self._get_list_commands(cmds_file), 'tests': {}}

        for comm in self._params['pre_commands']:
            splitted = comm.split('@')
            map(str.strip, splitted)
            id_ = splitted[0][1:]
            type_ = splitted[0][0]  # p, z or g

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
            # add name prefix and add 'underTest' hidden option to tell pyg2p that this is a test
            real_args += ['-n', type_]
            if not type_ == 'g':
                real_args += ['-U']
            real_args = ' '.join(real_args)  # back to string
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
        def _filter(line):
            return not (line.startswith('#') or line == '' or line == '\n')
        file_ = os.path.expanduser(file_)
        with open(file_) as f:
            commands = f.readlines()
        commands = [cmd.strip() for cmd in commands if _filter(cmd.strip())]
        return commands
