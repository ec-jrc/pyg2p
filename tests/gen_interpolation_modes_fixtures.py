"""
Generate golden fixtures for tests/test_interpolation_modes.py.

Runs the CURRENT implementation of each non-ADW interpolation mode on fixed,
deterministic inputs and stores the produced outputs under
tests/data/interpolation_modes/.

Run from the repository root:

    python -m tests.gen_interpolation_modes_fixtures

Only run this to (re)establish the reference behaviour on purpose. A test failure
should be investigated, not silenced by regenerating.

All interpolation modes are generated. 'bilinear' is included via SYNTHETIC_CASES
now that the library computes the 2-D cross product with a helper (previously it
raised under NumPy 2.x).
"""

import os

import numpy as np

from tests.test_interpolation_modes import (
    build_interpolator,
    synthetic_grid,
    build_cdd_interpolator,
    SYNTHETIC_CASES,
    CDD_CASES,
    DATA_DIR,
)


def _save(name, result, weights, indexes):
    path = os.path.join(DATA_DIR, name)
    np.savez(path,
             result=np.asarray(result),
             weights=np.asarray(weights),
             indexes=np.asarray(indexes))
    print(f"wrote {path}  (result shape {np.asarray(result).shape})")


def gen_synthetic():
    for case, params in SYNTHETIC_CASES.items():
        si = build_interpolator(params["mode"], num_of_splits=params["num_of_splits"])
        lonv, latv = synthetic_grid(params["nx"], params["ny"])
        result, weights, indexes = si.interpolate(lonv, latv)
        _save(f"{case}.npz", result, weights, indexes)


def gen_cdd():
    # Covers all three CDD sub-modes: MixHofstraShepard, Hofstra, NewEtAl.
    for case, cdd_mode in CDD_CASES.items():
        si, lonv, latv = build_cdd_interpolator(cdd_mode=cdd_mode)
        result, weights, indexes = si.interpolate(lonv, latv)
        _save(f"{case}.npz", result, weights, indexes)


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    gen_synthetic()
    gen_cdd()


if __name__ == "__main__":
    main()
