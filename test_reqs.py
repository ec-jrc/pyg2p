import os

OKGREEN = '\033[92m'
WARNING = '\033[93m'
FAIL = '\033[91m'
ENDC = '\033[0m'
BOLD = "\033[1m"

print WARNING + BOLD + '=================> Testing application environment' + ENDC
errs = []
warns = []

try:
    import main
    import util
    import util.files
    import main.exceptions
except ImportError, e:
    errs.append('=================XXXX> Core packages missing. Contact the developer soon!!!')

try:
    import datetime
except ImportError, e:
    errs.append('=================XXXX> datetime package missing')

try:
    import numpy
except ImportError, e:
    errs.append('=================XXXX> numpy package missing')

try:
    import numexpr
except ImportError, e:
    errs.append('=================XXXX> numexpr package missing')

try:
    import scipy.interpolate
except ImportError, e:
    errs.append('=================XXXX> scipy package missing')

try:

    import gdal
    from gdalconst import *
except ImportError, e:
    errs.append('=================XXXX> GDAL Python package missing')

try:
    import gribapi
except ImportError, e:
    errs.append('=================XXXX> gribapi python extension missing')

try:
    from scipy.spatial import cKDTree
except ImportError, e:
    errs.append('=================XXXX> scipy spatial cKDTree package missing')

try:
    import memory_profiler
except ImportError, e:
    warns.append('=================WARN> memory_profiler, you won''t be able to use test functionality')


dir_ = os.path.abspath(os.path.dirname(__file__))
if not (util.files.exists(dir_ + '/configuration/geopotentials', is_dir=True) and util.files.exists(dir_ + '/configuration/intertables', is_dir=True)):
    errs.append('=================XXXX> Important configuration folders are missing (geopotentials or intertables)!!!')

if not (util.files.exists(dir_ + '/configuration/geopotentials.xml') and util.files.exists(dir_+ '/configuration/parameters.xml') and util.files.exists(dir_+ '/configuration/logger-configuration.xml')):
    errs.append('=================XXXX> Important configuration files are missing (geopotentials.xml or parameters.xml)!!!')

if len(errs) > 0:
    print FAIL + BOLD + '=================> [ERROR] Some Requirements are missing!!!'
    import pprint as pp
    pp.pprint(errs)
    print ENDC

elif len(warns) > 0:
    print WARNING + BOLD + '=================> [WARN] Some optional requirements are missing!!!'
    import pprint as pp
    pp.pprint(warns)
    print ENDC
else:
    print OKGREEN + BOLD + '=================> [GOOD] All Requirements satisfied!!!' + ENDC