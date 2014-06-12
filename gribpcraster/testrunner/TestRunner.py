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
from gribpcraster.application.readers.PCRasterReader import PCRasterReader as pcr

OKGREEN = '\033[92m'
YELLOW = '\033[93m'
WARNING = '\033[94m'
FAIL = '\033[91m'
ENDC = '\033[0m'
BOLD = "\033[1m"


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
            FNULL = open(os.devnull, 'w')
            _run_job(comm, cwd=test_.out_dir, stdout=FNULL, stderr=STDOUT)
            print 'aguila ' + test_.out_dir + diff_map + ' ' + test_.out_dir + g_map + ' ' + test_.out_dir + p_map + ENDC
            reader_ = pcr(test_.out_dir + diff_map)
            diff_values = reader_.getValues()
            diff_values = diff_values[diff_values != reader_.getMissingValue()]
            # returns true if all elements are absolute(diff) <= atol
            all_ok = np.allclose(diff_values, np.zeros(diff_values.shape), atol=self._ctx.get('atol'))
            if all_ok:
                print OKGREEN + BOLD + '[GOOD] All values are good!' + ENDC
            else:
                array_ok = np.isclose(diff_values, np.zeros(diff_values.shape), atol=self._ctx.get('atol'))
                perc_wrong = float(array_ok[array_ok == False].size * 100) / float(diff_values.size)
                if perc_wrong > 5:  # more than 3% of differences
                    failed = True
                    print FAIL + BOLD + '[ERROR] {:3.4f}% of values are too different!'.format(perc_wrong) + ENDC
                else:
                    problematic = True
                    print WARNING + BOLD + '[WARN] values are very similar but with {:3.4f}% of differences!'.format(
                        perc_wrong) + ENDC
        if failed:
            return 1
        elif problematic:
            return 2
        else:
            return 0

    @staticmethod
    def _print_time_diffs(elapsed_counter_part, elapsed_pyg2p, test_, from_scipy=False):
        txt_ = 'pyg2p with scipy interpol ' if from_scipy else 'grib2pcraster'
        print YELLOW + BOLD + txt_ + ' test ' + test_.id + ' executed in ' + str(
            datetime.timedelta(seconds=elapsed_counter_part)) + ENDC
        differ_elaps = elapsed_pyg2p - elapsed_counter_part
        color_code = WARNING + BOLD
        if differ_elaps > 10:
            color_code = FAIL + BOLD
        if differ_elaps <= 0:
            color_code = OKGREEN + BOLD
            differ_elaps = - differ_elaps
        print color_code + 'Difference: ' + str(datetime.timedelta(seconds=differ_elaps)) + ENDC

    def run(self):
        diff_exec = self._ctx.get('pcrasterdiff.exec')
        ordered_tests = collections.OrderedDict(sorted(self._ctx.get('tests').iteritems(), key=lambda k: int(k[0])))
        elapsed_test = time.time()
        num_tests = 0
        results = {0: [], 1: [], 2: []}
        for key_, test_ in ordered_tests.iteritems():
            num_tests += 1
            elapsed_g2p = elapsed_pyg2p = elapsed_pyg2p_scipy = None
            print YELLOW + BOLD + "\n\n =====================> Running Test " + str(test_) + ENDC

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
                if p_num_maps != g_num_maps:
                    raw_input(
                        FAIL + BOLD + 'xxxxxxx! ATTENTION!!! Potential misconfiguration or bug! Number of maps are different p:' + str(
                            p_num_maps) + ' g:' + str(g_num_maps) + ENDC)

                print '\n\n====> Producing pcraster diff maps. Copy and paste aguila commands to compare them.'
                res = self.do_pcdiffs(diff_exec, test_, g_maps)
                results[res].append(test_.id)
            elif test_.pyg2p_scipy_command:
                print '\n\n====> Producing pcraster diff maps. Copy and paste aguila commands to compare them.'
                res = self.do_pcdiffs(diff_exec, test_, z_maps)
                results[res].append(test_.id)
            else:
                #test with only pyg2p commands. No comparisons.
                for p_map in p_maps:
                    print 'aguila ' + test_.out_dir + p_map

            print '\n\n' + YELLOW + BOLD + '=========== SUMMARY ==============' + ENDC
            print '\n' + YELLOW + BOLD + 'pyg2p test ' + test_.id + ' executed in ' + str(
                datetime.timedelta(seconds=elapsed_pyg2p)) + ENDC
            print YELLOW + BOLD + 'pyg2p memory usage: max {:6.2f}MB, avg {:6.2f}MB '.format(max_mem, avg_mem) + ENDC
            if elapsed_g2p:
                self._print_time_diffs(elapsed_g2p, elapsed_pyg2p, test_)
            elif elapsed_pyg2p_scipy:
                self._print_time_diffs(elapsed_pyg2p_scipy, elapsed_pyg2p, test_, from_scipy=True)
                print YELLOW + BOLD + 'pyg2p memory usage with scipy: max {:6.2f}MB, avg {:6.2f}MB '.format(
                    max_mem_scipy, avg_mem_scipy) + ENDC
            print '\n' + YELLOW + BOLD + '============= END ================' + ENDC + '\n'

        elapsed_test = time.time() - elapsed_test
        print '\n\n' + YELLOW + BOLD + '=========== TEST SUITE SUMMARY ==============' + ENDC
        print YELLOW + BOLD + '{} tests  executed in {}'.format(
            str(num_tests), str(datetime.timedelta(seconds=elapsed_test))) + ENDC
        print YELLOW + BOLD + 'successful {}, problematic: {}, failed: {}'.format(len(results[0]), len(results[2]), len(results[1]))
        print FAIL + BOLD + 'Failed tests: {}'.format(str(results[1])) + ENDC
        print WARNING + BOLD + 'Problematic tests: {}'.format(str(results[2])) + ENDC
        print OKGREEN + BOLD + 'Successful tests: {}'.format(str(results[0])) + ENDC
        print '\n' + YELLOW + BOLD + '=================== END ======================' + ENDC + '\n'