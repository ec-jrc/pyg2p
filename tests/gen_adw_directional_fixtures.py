"""
Generate golden fixtures for tests/test_adw_directional.py.

Runs the CURRENT implementation of
`adw_and_cdd_compute_weights_directional_in_broadcasting` and the ADW
`ScipyInterpolation.interpolate` path on a set of fixed, deterministic inputs,
and stores both the inputs and the produced outputs as .npz files under
tests/data/adw_directional/.

Run from the repository root:

    python -m tests.gen_adw_directional_fixtures

Only run this to (re)establish the reference behaviour on purpose. A test failure
should be investigated, not silenced by regenerating.
"""

import os

import numpy as np

# Reuse the exact same input builders as the tests so inputs never drift.
from tests.test_adw_directional import (
    make_directional_inputs,
    build_adw_interpolator,
    target_grid,
    INTERP_CASES,
    DATA_DIR,
)
from pyg2p.main.interpolation.scipy_interpolation_lib import (
    adw_and_cdd_compute_weights_directional_in_broadcasting as directional,
)


def gen_directional():
    for case in ("generic", "small", "with_zero_and_tie_rows"):
        inp = make_directional_inputs(case)
        out = np.asarray(directional(
            inp["s"], inp["latgrib"], inp["longrib"],
            inp["indexes"], inp["lat_inALL"], inp["lon_inALL"],
        ))
        # Store the caller-normalized output (np.nan_to_num(nan=1)). This is the
        # value the pipeline actually consumes, and it is identical for the
        # broadcasting and prange implementations (they differ only in how they
        # represent the degenerate 0/0 rows before this normalization). Storing the
        # normalized form keeps the test independent of that internal detail.
        out = np.nan_to_num(out, nan=1)
        path = os.path.join(DATA_DIR, f"directional_{case}.npz")
        np.savez(
            path,
            in_s=inp["s"],
            in_latgrib=inp["latgrib"],
            in_longrib=inp["longrib"],
            in_indexes=inp["indexes"],
            in_lat_inALL=inp["lat_inALL"],
            in_lon_inALL=inp["lon_inALL"],
            out_weight_directional=out,
        )
        print(f"wrote {path}  (out shape {out.shape})")


def gen_interpolate():
    for case, params in INTERP_CASES.items():
        si = build_adw_interpolator(
            seed=params["seed"],
            use_broadcasting=params["use_broadcasting"],
            num_of_splits=params["num_of_splits"],
        )
        lonv, latv = target_grid(params["nx"], params["ny"],
                                  params["lon0"], params["lon1"],
                                  params["lat0"], params["lat1"])
        result, weights, indexes = si.interpolate(lonv, latv)
        path = os.path.join(DATA_DIR, f"interpolate_{case}.npz")
        np.savez(path, result=result, weights=weights, indexes=indexes)
        print(f"wrote {path}  (result shape {result.shape})")


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    gen_directional()
    gen_interpolate()


if __name__ == "__main__":
    main()
