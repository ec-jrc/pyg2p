__author__ = 'dominik'

from gribpcraster.testrunner.TestContext import TestContext
from util.conversion.FromStringConversion import to_argv
import util.file.FileManager as fm
import os
from subprocess import call, STDOUT
from memory_profiler import memory_usage
import pyg2p
import time, datetime
import collections
import numpy as np
from gribpcraster.application.readers.PCRasterReader import PCRasterReader as pcraster_reader

ENDC = '\033[0m'
BOLD = "\033[1m"
G = '\033[92m' + BOLD
Y = '\033[93m' + BOLD
W = '\033[94m' + BOLD
R = '\033[91m' + BOLD


def _run_job(*args, **kwargs):
    call(*args, **kwargs)


def count_maps(param, out_dir):
    count = 0
    maps = []
    for i in os.listdir(out_dir):
        if i.startswith(param):
            count += 1
            maps.append(i)
    return count, maps


def print_colored(color, message):
        return color + message + ENDC


class TestRunner(object):
    def __init__(self, file_):
        self._ctx = TestContext(file_)

    def do_pcdiffs(self, diff_exec, test_, g_maps):

        failed = False
        problematic = False

        for g_map in g_maps:
            num_map = g_map[-3:]
            p_map = 'p' + g_map[1:]
            diff_map = 'diff.' + num_map

            comm = [diff_exec, diff_map + ' = ' + g_map + ' - ' + p_map]
            fnull = open(os.devnull, 'w')
            _run_job(comm, cwd=test_.out_dir, stdout=fnull, stderr=STDOUT)
            print 'aguila ' + test_.out_dir + diff_map + ' ' + test_.out_dir + g_map + ' ' + test_.out_dir + p_map
            reader_ = pcraster_reader(test_.out_dir + diff_map)
            diff_values = reader_.getValues()
            diff_values = diff_values[diff_values != reader_.getMissingValue()]
            # returns true if all elements are absolute(diff) <= atol
            all_ok = np.allclose(diff_values, np.zeros(diff_values.shape), atol=self._ctx.get('atol'))
            if all_ok:
                print print_colored(G, '[GOOD] All values are good!')
            else:
                array_ok = np.isclose(diff_values, np.zeros(diff_values.shape), atol=self._ctx.get('atol'))
                perc_wrong = float(array_ok[array_ok == False].size * 100) / float(diff_values.size)
                if perc_wrong > 5:  # more than 5% of differences
                    failed = True
                    print print_colored(R, '[ERROR] {:3.4f}% of values are too different!'.format(perc_wrong))
                elif 0.5 <= perc_wrong <= 5:
                    problematic = True
                    print print_colored(W, '[WARN] values are very similar but with {:3.4f}% of differences!'.format(perc_wrong))
                else:
                    print print_colored(G, '[GOOD] Almost all values are good [{:3.4f}% of differences]!'.format(perc_wrong))
        if failed:
            return 1
        elif problematic:
            return 2
        else:
            return 0

    @staticmethod
    def _print_time_diffs(elapsed_counter_part, elapsed_pyg2p, test_, from_scipy=False):
        txt_ = 'pyg2p with scipy interpol ' if from_scipy else 'grib2pcraster'
        print print_colored(Y, txt_ + ' test ' + test_.id + ' executed in ' + str(datetime.timedelta(seconds=elapsed_counter_part)))
        differ_elaps = elapsed_pyg2p - elapsed_counter_part
        color_code = W
        if differ_elaps > 10:
            color_code = R
        if differ_elaps <= 0:
            color_code = G
            differ_elaps = - differ_elaps
        print print_colored(color_code, 'Difference: ' + str(datetime.timedelta(seconds=differ_elaps)))

    def print_test_summary(self, avg_mem, avg_mem_scipy, elapsed_g2p, elapsed_pyg2p, elapsed_pyg2p_scipy, max_mem,
                           max_mem_scipy, test_):
        print print_colored(Y, '\n\n =========== SUMMARY ==============')
        print print_colored(Y, '\npyg2p test ' + test_.id + ' executed in ' + str(datetime.timedelta(seconds=elapsed_pyg2p)))
        print print_colored(Y, 'pyg2p memory usage: max {:6.2f}MB, avg {:6.2f}MB '.format(max_mem, avg_mem))
        if elapsed_g2p:
            self._print_time_diffs(elapsed_g2p, elapsed_pyg2p, test_)
        elif elapsed_pyg2p_scipy:
            self._print_time_diffs(elapsed_pyg2p_scipy, elapsed_pyg2p, test_, from_scipy=True)
            print print_colored(Y, 'pyg2p memory usage with scipy: max {:6.2f}MB, avg {:6.2f}MB '.format(max_mem_scipy, avg_mem_scipy))
        print '\n' + Y + '============= END ================' + ENDC + '\n'

    @staticmethod
    def print_test_suite_summary(elapsed_test, num_tests, results):
        elapsed_test = time.time() - elapsed_test
        print '\n\n\n' + print_colored(Y, '=========== TEST SUITE SUMMARY ==============')
        print print_colored(Y, '{} tests  executed in {}'.format(str(num_tests), str(datetime.timedelta(seconds=elapsed_test))))
        print print_colored(Y, 'successful {}, problematic: {}, failed: {}'.format(len(results[0]), len(results[2]), len(results[1])))
        print print_colored(R, 'Failed tests: {}'.format(str(results[1])))
        print print_colored(W, 'Problematic tests: {}'.format(str(results[2])))
        print print_colored(G, 'Successful tests: {}'.format(str(results[0])))
        print '\n' + print_colored(Y, '=================== END ======================') + '\n'

    def run(self):

        num_tests = g_num_maps = z_num_maps = avg_mem_scipy = max_mem_scipy = 0
        g_maps = z_maps = []
        results = {0: [], 1: [], 2: []}   # 0: succes, 1: errors, 2: problematic (with differences but up to 5%)

        ordered_tests = collections.OrderedDict(sorted(self._ctx.get('tests').iteritems(), key=lambda k: int(k[0])))
        elapsed_test = time.time()

        for key_, test_ in ordered_tests.iteritems():
            num_tests += 1
            elapsed_g2p = elapsed_pyg2p_scipy = None
            print print_colored(Y, "\n\n =====================> Running Test " + str(test_))

            if test_.g2p_command:
                fm.createDir(test_.out_dir, recreate=True)
                a = time.time()
                print 'Running grib2pcraster...'
                for g2p_comm in test_.g2p_command:
                    _run_job(to_argv(g2p_comm.strip()))
                elapsed_g2p = time.time() - a
                # get grib2pcraster output maps
                g_num_maps, g_maps = count_maps('g', test_.out_dir)

            if test_.pyg2p_scipy_command:
                print 'Running pyg2p with scipy interpolation...'
                a = time.time()
                t = (pyg2p.main, to_argv(test_.pyg2p_scipy_command.strip()))
                mem_usage = memory_usage(t)  # here it runs
                elapsed_pyg2p_scipy = time.time() - a
                avg_mem_scipy = sum(mem_usage) / len(mem_usage)
                max_mem_scipy = max(mem_usage)
                z_num_maps, z_maps = count_maps('g', test_.out_dir)

            print 'Running pyg2p...'
            a = time.time()
            t = (pyg2p.main, to_argv(test_.pyg2p_command.strip()))
            mem_usage = memory_usage(t)  # here it runs
            elapsed_pyg2p = time.time() - a
            avg_mem = sum(mem_usage) / len(mem_usage)
            max_mem = max(mem_usage)

            # get pyg2p output maps
            p_num_maps, p_maps = count_maps('p', test_.out_dir)

            if test_.g2p_command:
                self._check_maps(p_num_maps, test_, g_num_maps, g_maps, results)
            elif test_.pyg2p_scipy_command:
                self._check_maps(p_num_maps, test_, z_num_maps, z_maps, results)
            else:
                #test with only pyg2p commands. No comparisons.
                for p_map in p_maps:
                    print 'aguila ' + test_.out_dir + p_map

            self.print_test_summary(avg_mem, avg_mem_scipy, elapsed_g2p, elapsed_pyg2p, elapsed_pyg2p_scipy, max_mem, max_mem_scipy, test_)

        self.print_test_suite_summary(elapsed_test, num_tests, results)

    def _check_maps(self, p_num_maps, test_, o_num_maps, o_maps, results):
        if p_num_maps != o_num_maps:
            raw_input(print_colored(R, 'xxxxxxx! ATTENTION!!! Potential misconfiguration or bug! Number of maps are different p:' + str(p_num_maps) + ' g:' + str(o_num_maps)))

        print '\n\n====> Producing pcraster diff maps. Copy and paste aguila commands to compare them.'
        res = self.do_pcdiffs(self._ctx.get('pcrasterdiff.exec'), test_, o_maps)
        results[res].append(test_.id)