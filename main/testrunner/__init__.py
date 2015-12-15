import collections
import datetime
import os
import time
from subprocess import call, STDOUT

import numpy as np
from memory_profiler import memory_usage

import pyg2p
import util.files
from main.readers.pcraster import PCRasterReader
from main.testrunner.context import TestContext
from util.generics import GREEN, FAIL, WARN, YELLOW, ENDC, DEFAULT
from util.logger import Logger
from util.strings import to_argv


class TestRunner(object):
    
    def __init__(self, file_):
        self._ctx = TestContext(file_)

    def do_pcdiffs(self, diff_exec, test_, g_maps):

        failed = False
        problematic = False

        for g_map in g_maps:
            num_map = g_map[-3:]
            p_map = 'p{}'.format(g_map[1:])
            diff_map = 'diff.{}'.format(num_map)
            diff_map_cmd = '{} = {} - {}'.format(diff_map, g_map, p_map)
            comm = [diff_exec, diff_map_cmd]
            fnull = open(os.devnull, 'w')
            self._run_job(comm, cwd=test_.out_dir, stdout=fnull, stderr=STDOUT)
            reader_ = PCRasterReader(test_.out_dir + diff_map)
            diff_values = reader_.values()
            diff_values = diff_values[diff_values != reader_.missing_value]
            # returns true if all elements are absolute(diff) <= atol
            all_ok = np.allclose(diff_values, np.zeros(diff_values.shape), atol=self._ctx.get('atol'))
            # if all_ok:
            #     self._print_colored(GREEN, '[GOOD] All values are good!')
            if not all_ok:
                diff_map_path = os.path.join(test_.out_dir, diff_map)
                g_map_path = os.path.join(test_.out_dir, g_map)
                p_map_path = os.path.join(test_.out_dir, p_map)

                array_ok = np.isclose(diff_values, np.zeros(diff_values.shape), atol=self._ctx.get('atol'))
                perc_wrong = float(array_ok[array_ok == False].size * 100) / float(diff_values.size)
                if perc_wrong > 5:  # more than 5% of differences
                    failed = True
                    print 'aguila {} {} {}'.format(diff_map_path, g_map_path, p_map_path)
                    self._print_colored(FAIL, '[ERROR] {:3.4f}% of values are too different!'.format(perc_wrong))
                elif 0.5 <= perc_wrong <= 5:
                    problematic = True
                    print 'aguila {} {} {}'.format(diff_map_path, g_map_path, p_map_path)
                    self._print_colored(WARN, '[WARN] values are very similar but with {:3.4f}% of differences!'.format(perc_wrong))
        if failed:
            return '1'
        elif problematic:
            return '2'
        else:
            self._print_colored(GREEN, '[GOOD]')
            return '0'

    def _print_time_diffs(self, elapsed_counter_part, elapsed_pyg2p, test_, from_scipy=False):
        txt_ = 'pyg2p with scipy interpol ' if from_scipy else 'grib2pcraster'
        msg = '{} test {} executed in {}'.format(txt_, test_.id, str(datetime.timedelta(seconds=elapsed_counter_part)))
        self._print_colored(YELLOW, msg)
        differ_elaps = elapsed_pyg2p - elapsed_counter_part
        color_code = WARN
        if differ_elaps > 10:
            color_code = FAIL
        if differ_elaps <= 0:
            color_code = GREEN
            differ_elaps = - differ_elaps
        self._print_colored(color_code, 'Difference: {}'.format(str(datetime.timedelta(seconds=differ_elaps))))

    def print_test_summary(self, avg_mem, avg_mem_scipy, elapsed_g2p, elapsed_pyg2p, elapsed_pyg2p_scipy, max_mem,
                           max_mem_scipy, test_):
        self._print_colored(YELLOW, '\n\n =========== SUMMARY ==============')
        self._print_colored(YELLOW, '\nTest {} executed in {}'.format(test_.id, str(datetime.timedelta(seconds=elapsed_pyg2p))))
        self._print_colored(YELLOW, 'pyg2p memory usage: max {:6.2f}MB, avg {:6.2f}MB '.format(max_mem, avg_mem))
        if elapsed_g2p:
            self._print_time_diffs(elapsed_g2p, elapsed_pyg2p, test_)
        elif elapsed_pyg2p_scipy:
            self._print_colored(YELLOW, 'pyg2p memory usage with scipy: max {:6.2f}MB, avg {:6.2f}MB '.format(max_mem_scipy, avg_mem_scipy))
            self._print_time_diffs(elapsed_pyg2p_scipy, elapsed_pyg2p, test_, from_scipy=True)
        self._print_colored(YELLOW, '============= END ================')

    def print_test_suite_summary(self, elapsed_test, num_tests, results):
        elapsed_test = time.time() - elapsed_test
        self._print_colored(YELLOW, '\n\n\n=========== TEST SUITE SUMMARY ==============')
        self._print_colored(YELLOW, '{} tests  executed in {}'.format(str(num_tests), str(datetime.timedelta(seconds=elapsed_test))))
        self._print_colored(YELLOW, 'successful {}, problematic: {}, failed: {}'.format(len(results['0']), len(results['2']), len(results['1'])))
        self._print_colored(FAIL, 'Failed tests: {}'.format(str(results['1'])))
        self._print_colored(WARN, 'Problematic tests: {}'.format(str(results['2'])))
        self._print_colored(GREEN, 'Successful tests: {}'.format(str(results['0'])))
        self._print_colored(YELLOW, '\n\n=================== END ======================\n')

    def run(self):

        num_tests = g_num_maps = z_num_maps = avg_mem_scipy = max_mem_scipy = 0
        g_maps = z_maps = []
        results = {'0': [], '1': [], '2': []}   # 0: succes, 1: errors, 2: problematic (with differences but up to 5%)

        ordered_tests = collections.OrderedDict(sorted(self._ctx.get('tests').iteritems(), key=lambda k: int(k[0])))
        elapsed_test = time.time()

        for key_, test_ in ordered_tests.iteritems():
            num_tests += 1
            elapsed_g2p = elapsed_pyg2p_scipy = None
            self._print_colored(DEFAULT, '\n\n =====================> Running Test {}'.format(test_))
            util.files.delete_files_from_dir(test_.out_dir)

            if test_.g2p_command:
                util.files.create_dir(test_.out_dir, recreate=True)
                a = time.time()
                print 'Running grib2pcraster...'
                for g2p_comm in test_.g2p_command:
                    self._run_job(to_argv(g2p_comm.strip()))
                elapsed_g2p = time.time() - a
                # get grib2pcraster output maps
                g_num_maps, g_maps = self._count_maps('g', test_.out_dir)

            if test_.pyg2p_scipy_command:
                print 'Running pyg2p with scipy interpolation...'
                a = time.time()
                t = (pyg2p.main, to_argv(test_.pyg2p_scipy_command.strip()))
                mem_usage = memory_usage(t)  # here it runs
                elapsed_pyg2p_scipy = time.time() - a
                avg_mem_scipy = sum(mem_usage) / len(mem_usage)
                max_mem_scipy = max(mem_usage)
                z_num_maps, z_maps = self._count_maps('z', test_.out_dir)

            print 'Running pyg2p...'
            a = time.time()

            t = (pyg2p.main, to_argv(test_.pyg2p_command.strip()))
            mem_usage = memory_usage(t)  # here it runs
            elapsed_pyg2p = time.time() - a
            avg_mem = sum(mem_usage) / len(mem_usage)
            max_mem = max(mem_usage)

            # get pyg2p output maps
            p_num_maps, p_maps = self._count_maps('p', test_.out_dir)

            if test_.g2p_command:
                self._check_maps(p_num_maps, test_, g_num_maps, g_maps, results)
            elif test_.pyg2p_scipy_command:
                self._check_maps(p_num_maps, test_, z_num_maps, z_maps, results)
            else:
                # test with only pyg2p commands. No comparisons.
                for p_map in p_maps:
                    print 'aguila {}'.format(os.path.join(test_.out_dir, p_map))

            self.print_test_summary(avg_mem, avg_mem_scipy, elapsed_g2p, elapsed_pyg2p, elapsed_pyg2p_scipy, max_mem, max_mem_scipy, test_)

        self.print_test_suite_summary(elapsed_test, num_tests, results)
        Logger.reset_logger()

    def _check_maps(self, p_num_maps, test_, o_num_maps, o_maps, results):
        if p_num_maps != o_num_maps:
            self._print_colored(FAIL, 'xxxxxxx! ATTENTION!!! Potential misconfiguration or bug!')
            self._print_colored(FAIL, 'Number of maps are different p: {} g: {}'.format(p_num_maps, o_num_maps))
            results['1'].append(test_.id)
        else:
            print '\n\n====> Producing pcraster diff maps. If values are not identical, will print aguila commands to compare them.'
            res = self.do_pcdiffs(self._ctx.get('pcrasterdiff.exec'), test_, o_maps)
            results[res].append(test_.id)

    @staticmethod
    def _print_colored(color, message):
        print color + message + ENDC

    @staticmethod
    def _run_job(*args, **kwargs):
        call(*args, **kwargs)

    @staticmethod
    def _count_maps(param, out_dir):
        count = 0
        maps = []
        for i in os.listdir(out_dir):
            if i.startswith(param):
                count += 1
                maps.append(i)
        return count, maps
