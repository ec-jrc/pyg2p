"""
Characterization (golden-value) unit tests for the scipy interpolation modes
other than ADW (which is covered in test_adw_directional.py).

Modes handled here
------------------
`ScipyInterpolation.interpolate` dispatches on ``mode``:

    nearest            -> _build_nn                     (nnear = 1)
    invdist            -> _build_weights_invdist (IDW)  (nnear = 20)
    adw                -> _build_weights_invdist (Shepard)  [see test_adw_directional.py]
    cdd                -> _build_weights_invdist (CDD)  (nnear = 11, needs a CDD map)
    bilinear           -> _build_weights_bilinear       (nnear = 4)
    triangulation      -> _build_weights_triangulation  (nnear = 3)
    bilinear_delaunay  -> _build_weights_triangulation(use_bilinear=True)  (nnear = 4)

Strategy (identical to test_adw_directional.py)
-----------------------------------------------
Each mode runs on FIXED, deterministic inputs; the produced outputs were captured
once from the current implementation and stored as golden fixtures under
``tests/data/interpolation_modes/``. The tests load the fixed inputs, run the code,
and assert it reproduces the stored outputs. Tolerances are loose enough to absorb
cross-platform floating-point reassociation (different CPU / BLAS / thread count)
while still catching any real change in behaviour.

Mode-specific notes
-------------------
* ``cdd`` is tightly coupled to a CDD map whose raveled size must equal the target
  grid. We reuse the existing fixtures ``tests/data/cdd_temp_map.nc`` (map) and
  ``tests/data/template_test.nc`` (600x600 grid). It is heavier than the other
  cases but still a single deterministic pass. All three CDD sub-modes are
  covered: 'MixHofstraShepard' (default), 'Hofstra', and 'NewEtAl'.
* ``bilinear`` runs on synthetic data like the other modes. (It previously failed
  under NumPy 2.x because ``_build_weights_bilinear`` used ``numpy.cross`` on 2-D
  vectors; that is now computed via a small ``cross2d`` helper in the library.)

Regenerating the fixtures
-------------------------
    python -m tests.gen_interpolation_modes_fixtures

Do NOT regenerate merely to make a failing test pass: a diff means the numerical
output changed, which is exactly what these tests exist to flag.
"""

import os

import numpy as np
import pytest

from pyg2p.main.interpolation.scipy_interpolation_lib import ScipyInterpolation
from pyg2p.main.readers.netcdf import NetCDFReader

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data', 'interpolation_modes')

# Cross-platform tolerances (see test_adw_directional.py for rationale).
RTOL = 1e-9
ATOL = 1e-11

# nnear per mode, matching Interpolator / Config.INTERPOLATION_MODES.
NNEAR = {"nearest": 1, "invdist": 20, "cdd": 11,
         "bilinear": 4, "triangulation": 3, "bilinear_delaunay": 4}

# Paths to the shared fixtures used only by the CDD case.
CDD_MAP = os.path.join(os.path.dirname(__file__), 'data', 'cdd_temp_map.nc')
CDD_GRID = os.path.join(os.path.dirname(__file__), 'data', 'template_test.nc')


def _load(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        pytest.skip(
            f"Golden fixture missing: {path}. "
            f"Generate it with: python -m tests.gen_interpolation_modes_fixtures"
        )
    return np.load(path, allow_pickle=False)


# ---------------------------------------------------------------------------
# Fixed input builders (MUST stay identical to the generator module)
# ---------------------------------------------------------------------------

def build_interpolator(mode, seed=123, n_stations=400, use_broadcasting=True,
                       num_of_splits=None, **kwargs):
    """Deterministic ScipyInterpolation over synthetic stations for a given mode."""
    rng = np.random.default_rng(seed)
    latgrib = rng.uniform(30.0, 60.0, size=n_stations)
    longrib = rng.uniform(-10.0, 30.0, size=n_stations)
    source_values = rng.uniform(0.0, 50.0, size=n_stations)
    grid_details = {'gridType': 'NOT rotated', 'Nj': 1, 'radius': 6367470.0}
    si = ScipyInterpolation(
        longrib, latgrib, grid_details, source_values,
        nnear=NNEAR[mode], mv_target=-9999.0, mv_source=-9999.0,
        target_is_rotated=False, parallel=False, mode=mode,
        use_broadcasting=use_broadcasting, num_of_splits=num_of_splits, **kwargs)
    return si


def synthetic_grid(nx, ny, lon0=-8.0, lon1=28.0, lat0=32.0, lat1=58.0):
    lon = np.linspace(lon0, lon1, nx)
    lat = np.linspace(lat0, lat1, ny)
    return np.meshgrid(lon, lat)


def build_cdd_interpolator(cdd_mode='MixHofstraShepard', seed=123, n_stations=500):
    """CDD interpolator wired to the committed CDD map + matching target grid.

    ``cdd_mode`` selects the CDD sub-algorithm: 'MixHofstraShepard' (default),
    'Hofstra', or 'NewEtAl'.
    """
    grid = NetCDFReader(CDD_GRID)
    latv, lonv = grid.get_lat_lon_values()
    rng = np.random.default_rng(seed)
    latgrib = rng.uniform(float(latv.min()), float(latv.max()), size=n_stations)
    longrib = rng.uniform(float(lonv.min()), float(lonv.max()), size=n_stations)
    source_values = rng.uniform(0.0, 50.0, size=n_stations)
    grid_details = {'gridType': 'NOT rotated', 'Nj': 1, 'radius': 6367470.0}
    si = ScipyInterpolation(
        longrib, latgrib, grid_details, source_values,
        nnear=NNEAR["cdd"], mv_target=-9999.0, mv_source=-9999.0,
        target_is_rotated=False, parallel=False, mode='cdd',
        use_broadcasting=True, num_of_splits=None,
        cdd_map=CDD_MAP, cdd_mode=cdd_mode, cdd_options=None)
    return si, lonv, latv


# Fixed scenarios that run with purely synthetic data.
# Kept in sync with gen_interpolation_modes_fixtures.py.
SYNTHETIC_CASES = {
    "nearest":           dict(mode="nearest",           nx=20, ny=16, num_of_splits=None),
    "invdist":           dict(mode="invdist",           nx=20, ny=16, num_of_splits=None),
    "invdist_splits":    dict(mode="invdist",           nx=30, ny=24, num_of_splits=4),
    "bilinear":          dict(mode="bilinear",          nx=20, ny=16, num_of_splits=None),
    "triangulation":     dict(mode="triangulation",     nx=20, ny=16, num_of_splits=None),
    "bilinear_delaunay": dict(mode="bilinear_delaunay", nx=20, ny=16, num_of_splits=None),
}


# ---------------------------------------------------------------------------
# 1) Synthetic-data modes
# ---------------------------------------------------------------------------

class TestSyntheticModesGolden:

    @pytest.mark.parametrize("case", list(SYNTHETIC_CASES.keys()))
    def test_matches_golden(self, case):
        params = SYNTHETIC_CASES[case]
        golden = _load(f"{case}.npz")

        si = build_interpolator(params["mode"], num_of_splits=params["num_of_splits"])
        lonv, latv = synthetic_grid(params["nx"], params["ny"])
        result, weights, indexes = si.interpolate(lonv, latv)

        np.testing.assert_allclose(np.asarray(result), golden["result"],
                                   rtol=RTOL, atol=ATOL, equal_nan=True)
        np.testing.assert_allclose(np.asarray(weights), golden["weights"],
                                   rtol=RTOL, atol=ATOL, equal_nan=True)
        np.testing.assert_array_equal(np.asarray(indexes), golden["indexes"])

    @pytest.mark.parametrize("case", list(SYNTHETIC_CASES.keys()))
    def test_result_shape(self, case):
        params = SYNTHETIC_CASES[case]
        si = build_interpolator(params["mode"], num_of_splits=params["num_of_splits"])
        lonv, latv = synthetic_grid(params["nx"], params["ny"])
        result, _, _ = si.interpolate(lonv, latv)
        assert np.asarray(result).shape == (lonv.size,)


# ---------------------------------------------------------------------------
# 2) CDD mode (uses committed map + grid fixtures)
# ---------------------------------------------------------------------------

# All three CDD sub-modes, each golden-tested.
CDD_CASES = {
    "cdd": "MixHofstraShepard",   # fixture name kept as 'cdd' for backward compat
    "cdd_hofstra": "Hofstra",
    "cdd_newetal": "NewEtAl",
}


class TestCddGolden:

    @pytest.mark.parametrize("case,cdd_mode", list(CDD_CASES.items()))
    def test_cdd_matches_golden(self, case, cdd_mode):
        golden = _load(f"{case}.npz")
        si, lonv, latv = build_cdd_interpolator(cdd_mode=cdd_mode)
        result, weights, indexes = si.interpolate(lonv, latv)
        np.testing.assert_allclose(np.asarray(result), golden["result"],
                                   rtol=RTOL, atol=ATOL, equal_nan=True)
        np.testing.assert_allclose(np.asarray(weights), golden["weights"],
                                   rtol=RTOL, atol=ATOL, equal_nan=True)
        np.testing.assert_array_equal(np.asarray(indexes), golden["indexes"])
