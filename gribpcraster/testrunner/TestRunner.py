__author__ = 'dominik'

from gribpcraster.testrunner.TestContext import TestContext
from util.conversion.FromStringConversion import to_argv
import util.file.FileManager as fm
import os
from subprocess import call, STDOUT
import pyg2p
import time, datetime
import collections
import numpy as np
from gribpcraster.application.readers.PCRasterReader import PCRasterReader as pcr

OKGREEN = '\033[92m'
WARNING = '\033[93m'
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
        for g_map in g_maps:
            num_map = g_map[-3:]
            p_map = 'p' + g_map[1:]
            diff_map = 'diff.' + num_map

            comm = [diff_exec, diff_map + ' = ' + g_map + ' - ' + p_map]
            FNULL = open(os.devnull, 'w')
            _run_job(comm, cwd=test_.out_dir, stdout=FNULL, stderr=STDOUT)
            print BOLD + 'aguila ' + test_.out_dir + diff_map + ' ' + test_.out_dir + g_map + ' ' + test_.out_dir + p_map + ENDC
            reader_ = pcr(test_.out_dir + diff_map)
            diff_values = reader_.getValues()

            diff_values = diff_values[diff_values != reader_.getMissingValue()]
            # returns true if all elements are absolute(diff) <= atol
            all_ok = np.allclose(diff_values, np.zeros(diff_values.shape), atol=self._ctx.get('atol'))
            if all_ok:
                print OKGREEN + BOLD + '[GOOD] values are good!' + ENDC
            else:
                print FAIL + BOLD + '[ERROR] values are too different!' + ENDC

    def run(self):
        diff_exec = self._ctx.get('pcrasterdiff.exec')
        ordered_tests = collections.OrderedDict(sorted(self._ctx.get('tests').items(), key=lambda k: int(k[0])))
        for key_, test_ in ordered_tests.iteritems():
            print WARNING + BOLD + "\n\n =====================> Running Test " + str(test_) + ENDC

            if test_.g2p_command:
                a = time.time()
                print '\n\nCreating out g2p directory or deleting old g2p output...'
                fm.createDir(test_.out_dir, recreate=True, prefix_='g')
                print 'Running grib2pcraster...'
                for g2p_comm in test_.g2p_command:
                    _run_job(to_argv(g2p_comm.strip()))
                elapsed = time.time() - a
                print BOLD + 'grib2pcraster test ' + test_.id + ' executed in ' + str(
                    datetime.timedelta(seconds=elapsed)) + ENDC
                g_num_maps, g_maps = count_maps('g', test_.out_dir)

            print '\n\nCreating out pyg2p directory or deleting old pyg2p output'
            fm.createDir(test_.out_dir, recreate=True, prefix_='p')
            print 'Running pyg2p...'
            a = time.time()
            pyg2p.main(to_argv(test_.pyg2p_command.strip()))
            elapsed = time.time() - a
            print BOLD + 'pyg2p test ' + test_.id + ' executed in ' + str(datetime.timedelta(seconds=elapsed)) + ENDC
            p_num_maps, p_maps = count_maps('p', test_.out_dir)

            if test_.g2p_command:
                if p_num_maps != g_num_maps:
                    raw_input(
                        FAIL + BOLD + 'xxxxxxx! ATTENTION!!! Potential misconfiguration or bug! Number of maps are different p:' + str(
                            p_num_maps) + ' g:' + str(g_num_maps) + ENDC)

                print '\n\n====> Producing pcraster diff maps. Copy and paste aguila commands to compare them.'

                self.do_pcdiffs(diff_exec, test_, g_maps)
            else:
                for p_map in p_maps:
                    print BOLD + 'aguila ' + test_.out_dir + p_map + ENDC


