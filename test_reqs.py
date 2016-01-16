from util.generics import WARN, BOLD, FAIL, ENDC, GREEN


def test_reqs():

    print WARN + BOLD + '=================> Testing application environment' + ENDC
    errs = []

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
        import gdalconst
    except ImportError, e:
        errs.append('=================XXXX> GDAL Python package missing')

    try:
        import gribapi
    except ImportError, e:
        errs.append('=================XXXX> gribapi python extension missing')

    if len(errs) > 0:
        print FAIL + BOLD + '=================> [ERROR] Some Requirements are missing!!!'
        print('\n'.join(errs))
        print ENDC
    else:
        print GREEN + BOLD + '=================> [GOOD] All Requirements satisfied!!!' + ENDC