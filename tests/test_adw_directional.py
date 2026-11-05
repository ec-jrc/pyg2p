"""
Characterization (golden-value) unit tests for the ADW directional-weight
computation and the code that depends on it.

Target under test
------------------
`adw_and_cdd_compute_weights_directional_in_broadcasting` computes, for every
target cell `c` and each of its `k` nearest-neighbour stations `i`, a directional
weight:

    weight_directional[c, i] = sum_{j != i} (1 - cos_theta[c, i, j]) * s[c, j]
                               / sum_{j != i} s[c, j]

where `cos_theta[c, i, j]` is the cosine of the angle, seen from cell `c`, between
the directions to station `i` and to station `j` (in lat/lon space), and `s` are
the Shepard distance coefficients. The caller
`ScipyInterpolation._build_weights_invdist` (ADW/Shepard mode) uses it to build the
final interpolation weights and interpolated values.

Strategy
--------
These are characterization tests: a set of FIXED, deterministic inputs is paired
with REFERENCE outputs that were captured once from the current implementation and
stored as golden fixtures under ``tests/data/adw_directional/``. The tests load the
fixed inputs, run the current code, and assert it reproduces the stored outputs.

This locks the observable behaviour of:
  * ``adw_and_cdd_compute_weights_directional_in_broadcasting`` (direct), and
  * the full ``ScipyInterpolation.interpolate`` ADW path that calls it (dependent),

so any future change that alters results is caught.

Regenerating the fixtures
-------------------------
If the reference behaviour intentionally changes, regenerate the golden files with:

    python -m tests.gen_adw_directional_fixtures

Do NOT regenerate them merely to make a failing test pass: a diff here means the
numerical output changed, which is exactly what these tests exist to flag.
"""

import os

import numpy as np
import pytest

from pyg2p.main.interpolation.scipy_interpolation_lib import (
    adw_and_cdd_compute_weights_directional_in_broadcasting as directional,
)
from pyg2p.main.interpolation.scipy_interpolation_lib import ScipyInterpolation

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data', 'adw_directional')

# Tolerances for comparing against stored golden values. The computation and the
# stored values are float64. Results are NOT bit-reproducible across machines:
# different CPUs, BLAS backends, and numba thread counts reorder the floating-point
# reductions (the per-row sums / einsum), so the last few bits differ. These
# tolerances are loose enough to absorb that reassociation noise on float64 while
# still catching any real change in behaviour (which shifts results far more than
# a few ulps). If a port shows larger-but-still-benign drift, relax RTOL first.
RTOL = 1e-9
ATOL = 1e-11


def _load(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        pytest.skip(
            f"Golden fixture missing: {path}. "
            f"Generate it with: python -m tests.gen_adw_directional_fixtures"
        )
    return np.load(path, allow_pickle=False)


# ---------------------------------------------------------------------------
# Fixed input builders (MUST stay identical to gen_adw_directional_fixtures.py)
# ---------------------------------------------------------------------------

def make_directional_inputs(case):
    """Deterministic inputs for the directional function, keyed by case name."""
    if case == "generic":
        rng = np.random.default_rng(1001)
        n, k, ns = 250, 11, 300
    elif case == "small":
        rng = np.random.default_rng(1002)
        n, k, ns = 7, 11, 40
    elif case == "with_zero_and_tie_rows":
        rng = np.random.default_rng(1003)
        n, k, ns = 60, 11, 120
    else:
        raise ValueError(case)

    latgrib = rng.uniform(20.0, 70.0, size=ns)
    longrib = rng.uniform(-25.0, 45.0, size=ns)
    indexes = rng.integers(0, ns, size=(n, k))
    lat_in = rng.uniform(20.0, 70.0, size=n)
    lon_in = rng.uniform(-25.0, 45.0, size=n)
    s = rng.uniform(0.0, 1.0, size=(n, k))

    if case == "with_zero_and_tie_rows":
        s[0, :] = 0.0            # all-zero row -> 0/0 for every neighbour
        s[1, :] = 0.0
        s[2, :] = 0.0
        s[2, 4] = 0.9            # only one contributing station
    return dict(s=s, latgrib=latgrib, longrib=longrib,
                indexes=indexes, lat_inALL=lat_in, lon_inALL=lon_in)


def build_adw_interpolator(seed, use_broadcasting, num_of_splits, n_stations=400):
    """Deterministic ADW ScipyInterpolation over synthetic stations."""
    rng = np.random.default_rng(seed)
    latgrib = rng.uniform(30.0, 60.0, size=n_stations)
    longrib = rng.uniform(-10.0, 30.0, size=n_stations)
    source_values = rng.uniform(0.0, 50.0, size=n_stations)
    grid_details = {'gridType': 'NOT rotated', 'Nj': 1, 'radius': 6367470.0}
    si = ScipyInterpolation(
        longrib, latgrib, grid_details, source_values,
        nnear=11, mv_target=-9999.0, mv_source=-9999.0,
        target_is_rotated=False, parallel=False, mode='adw',
        use_broadcasting=use_broadcasting, num_of_splits=num_of_splits,
    )
    si.min_upper_bound = 1e8
    return si


def target_grid(nx, ny, lon0, lon1, lat0, lat1):
    lon = np.linspace(lon0, lon1, nx)
    lat = np.linspace(lat0, lat1, ny)
    lonv, latv = np.meshgrid(lon, lat)
    return lonv, latv


# Fixed interpolation scenarios (name -> params). Kept in sync with the generator.
#
# The *_broadcast cases drive the jitted broadcasting directional function; the
# *_loop cases set use_broadcasting=False, which exercises the pure-NumPy
# directional loop inside _build_weights_invdist instead. Covering both makes sure
# the two directional code paths in the ADW/Shepard mode stay pinned.
INTERP_CASES = {
    "splits_broadcast": dict(seed=123, use_broadcasting=True, num_of_splits=4,
                             nx=30, ny=24, lon0=-8.0, lon1=28.0, lat0=32.0, lat1=58.0),
    "no_splits_broadcast": dict(seed=123, use_broadcasting=True, num_of_splits=None,
                                nx=20, ny=16, lon0=-8.0, lon1=28.0, lat0=32.0, lat1=58.0),
    "splits_loop": dict(seed=123, use_broadcasting=False, num_of_splits=4,
                        nx=30, ny=24, lon0=-8.0, lon1=28.0, lat0=32.0, lat1=58.0),
    "no_splits_loop": dict(seed=123, use_broadcasting=False, num_of_splits=None,
                           nx=20, ny=16, lon0=-8.0, lon1=28.0, lat0=32.0, lat1=58.0),
}


# ---------------------------------------------------------------------------
# 1) Direct golden-value tests for the directional function
# ---------------------------------------------------------------------------

class TestDirectionalGolden:

    @pytest.mark.parametrize("case", ["generic", "small", "with_zero_and_tie_rows"])
    def test_matches_golden(self, case):
        inp = make_directional_inputs(case)
        golden = _load(f"directional_{case}.npz")

        # Inputs must match exactly what was used to produce the golden output.
        for key in ("s", "latgrib", "longrib", "indexes", "lat_inALL", "lon_inALL"):
            np.testing.assert_array_equal(
                inp[key], golden[f"in_{key}"],
                err_msg=f"Fixed input '{key}' drifted from the stored fixture for case '{case}'",
            )

        out = np.asarray(directional(
            inp["s"], inp["latgrib"], inp["longrib"],
            inp["indexes"], inp["lat_inALL"], inp["lon_inALL"],
        ))
        # Compare at the caller-normalized level. The caller
        # (ScipyInterpolation._build_weights_invdist) always applies
        # np.nan_to_num(..., nan=1) to the directional weights before using them, so
        # that is the output that actually matters downstream. Comparing the
        # normalized form makes this test independent of how a given implementation
        # represents the degenerate "only one contributing station" rows internally
        # (the broadcasting version leaves a raw 0/0 NaN there; the prange version
        # writes 1.0 directly). Both agree after nan_to_num.
        np.testing.assert_allclose(
            np.nan_to_num(out, nan=1), golden["out_weight_directional"],
            rtol=RTOL, atol=ATOL,
        )

    def test_output_shape(self):
        inp = make_directional_inputs("generic")
        out = np.asarray(directional(
            inp["s"], inp["latgrib"], inp["longrib"],
            inp["indexes"], inp["lat_inALL"], inp["lon_inALL"],
        ))
        assert out.shape == inp["indexes"].shape


# ---------------------------------------------------------------------------
# 2) Golden-value tests for the dependent code path (ScipyInterpolation.interpolate)
# ---------------------------------------------------------------------------

class TestInterpolateAdwGolden:

    @pytest.mark.parametrize("case", list(INTERP_CASES.keys()))
    def test_interpolate_matches_golden(self, case):
        params = INTERP_CASES[case]
        golden = _load(f"interpolate_{case}.npz")

        si = build_adw_interpolator(
            seed=params["seed"],
            use_broadcasting=params["use_broadcasting"],
            num_of_splits=params["num_of_splits"],
        )
        lonv, latv = target_grid(params["nx"], params["ny"],
                                  params["lon0"], params["lon1"],
                                  params["lat0"], params["lat1"])
        result, weights, indexes = si.interpolate(lonv, latv)

        np.testing.assert_allclose(result, golden["result"],
                                   rtol=RTOL, atol=ATOL, equal_nan=True)
        np.testing.assert_allclose(weights, golden["weights"],
                                   rtol=RTOL, atol=ATOL, equal_nan=True)
        # Neighbour indexes are compared exactly: the synthetic station coordinates
        # are random float64, so there are no equidistant ties for the KDTree to
        # break differently across SciPy builds. If a future scenario introduces
        # ties, compare sorted rows (or the resulting values) instead of raw order.
        np.testing.assert_array_equal(indexes, golden["indexes"])
