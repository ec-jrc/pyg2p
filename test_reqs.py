from util.generics import WARN, BOLD, FAIL, ENDC, GREEN

print WARN + BOLD + '=================> Testing application environment' + ENDC
errs = []
warns = []

try:
    import numpy
except ImportError, e:
    errs.append('=================XXXX> numpy package missing')

try:
    import numexpr
except ImportError, e:
    errs.append('=================XXXX> numexpr package missing')

try:
    import scipy
except ImportError, e:
    errs.append('=================XXXX> scipy package missing')
else:
    try:
        from scipy.spatial import cKDTree
    except ImportError, e:
        errs.append('=================XXXX> scipy spatial cKDTree package missing')

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
    import memory_profiler
except ImportError, e:
    warns.append('=================WARN> memory_profiler, you won''t be able to use test functionality')


if len(errs) > 0:
    print FAIL + BOLD + '=================> [ERROR] Some Requirements are missing!!!'
    import pprint as pp
    pp.pprint(errs)
    print ENDC

elif len(warns) > 0:
    print WARN + BOLD + '=================> [WARN] Some optional requirements are missing!!!'
    import pprint as pp
    pp.pprint(warns)
    print ENDC
else:
    print GREEN + BOLD + '=================> [GOOD] All Requirements satisfied!!!' + ENDC