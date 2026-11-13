"""
End-to-end unit tests that run pyg2p through a *real JSON command file*.

Unlike ``test_api.py`` (which drives pyg2p from an in-memory ``ApiContext`` dict)
and ``test_interpolation.py`` (which calls the ``Interpolator`` directly), the
tests here exercise the full CLI path:

    JSON command file  ->  Command / run_command  ->  pyg2p_exe  ->  Controller
                       ->  interpolation + conversion/aggregation  ->  output maps

The JSON command files are *committed* under ``tests/data/jsons/`` and fed to
pyg2p via ``-c`` exactly like a user would on the command line. They use repo
relative paths (``tests/data/...``), so the tests must run from the repository
root (pytest's rootdir), which is where the suite already runs. All inputs come
from the existing fixtures under ``tests/data``:

    input.grib   5 GRIB messages of ``2t`` (steps 0/6/12/18/24), rotated_ll grid,
                 perturbationNumber 2.
    lat.map      810x680 PCRaster target latitude map.
    lon.map      810x680 PCRaster target longitude map.
    dem.map      810x680 PCRaster clone/DEM map.

Interpolation mode
------------------
The ``nearest`` configs reuse the intertable already committed in the repo
(``tests/data/tbl_pf10slhf_550800_scipy_nearest.npy.gz``). That keeps those tests
fast, deterministic and side-effect free: the JSON ``@intertableDir`` points at
``tests/data`` and no new table is written.

The ``invdist`` and ``adw`` configs have no committed intertable, so those tests
are marked ``slow`` (need ``-X/--runslow``). They create the table inside a
throwaway temp dir (``-N/--intertableDir`` on the command line overrides the JSON)
and redirect ``UserConfiguration.config_dir`` to a throwaway ``.pyg2p``, so neither
the repo nor the real user configuration is touched.
"""

import os
import json
import glob
import tempfile

import numpy as np
import pytest

from pyg2p.main.api import Command, run_command
from pyg2p.main.readers.pcr import PCRasterReader


TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(TESTS_DIR, 'data')
JSONS_DIR = os.path.join(DATA_DIR, 'jsons')
# The committed JSON command files use repo-relative paths (tests/data/...),
# which pyg2p resolves against the current working directory.
REPO_ROOT = os.path.dirname(TESTS_DIR)

INPUT_GRIB = os.path.join(DATA_DIR, 'input.grib')

# PCRaster missing value written by pyg2p for cells outside the valid area.
PCR_MV = -3.4028234663852886e+38

# input.grib carries 5 steps of 2t (0, 6, 12, 18, 24).
N_STEPS = 5
# Target grid defined by lat/lon/dem maps.
TARGET_SHAPE = (810, 680)
# eps member present in input.grib.
EPS_MEMBER = 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _json(name):
    """Absolute path to a committed JSON command file under tests/data/jsons/."""
    path = os.path.join(JSONS_DIR, name)
    assert os.path.exists(path), f"Missing committed command file: {path}"
    return path


def _run(cmd_file, out_dir, create_intertable=False, intertable_dir=None):
    """Run pyg2p against a committed JSON command file via the CLI Command builder."""
    cmd = (Command()
           .with_cmdpath(cmd_file)
           .with_inputfile(INPUT_GRIB)
           .with_outdir(out_dir)
           .with_eps(EPS_MEMBER)
           .with_log_level('ERROR'))
    if intertable_dir:
        cmd = cmd.with_intertable_dir(intertable_dir)
    if create_intertable:
        cmd = cmd.with_create_intertable()
    return run_command(cmd)


def _pcr_outputs(out_dir, prefix='pg'):
    return sorted(glob.glob(os.path.join(out_dir, f'{prefix}*')))


class _FakeGlobalConf:
    """Minimal stand-in for GlobalConf so global intertable/geopotential dirs
    resolve to our temp dir instead of the unset (None) package defaults."""
    def __init__(self, tables_dir):
        self.vars = {'intertables': tables_dir, 'geopotentials': tables_dir}


def _setup_throwaway_config(monkeypatch, tmp_dir):
    """Point pyg2p at a throwaway ~/.pyg2p and a temp intertables dir.

    Returns the intertables dir. Creating an intertable via the CLI requires an
    ``INTERTABLES`` path in a ``.conf`` file (resolved from
    ``UserConfiguration.config_dir``), and the intertable-id resolution also joins
    the *global* intertables dir, which is unset (None) in the installed package.
    We therefore redirect the user config dir to a temp ``.pyg2p`` and preseed the
    ``GlobalConf`` singleton so the global dir points at the same temp dir. Nothing
    touches the repo or the real user configuration.
    """
    from pyg2p.main.config import UserConfiguration, GlobalConf

    conf_dir = os.path.join(tmp_dir, 'pyg2p_conf') + os.sep
    os.makedirs(conf_dir)
    tables_dir = os.path.join(tmp_dir, 'intertables')
    os.makedirs(tables_dir)
    with open(os.path.join(conf_dir, 'paths.conf'), 'w') as f:
        f.write(f'INTERTABLES={tables_dir}\n')
        f.write(f'GEOPOTENTIALS={tables_dir}\n')
    monkeypatch.setattr(UserConfiguration, 'config_dir', conf_dir)
    # Replace the cached GlobalConf singleton so global_data_path != None.
    monkeypatch.setattr(GlobalConf, 'instance', _FakeGlobalConf(tables_dir))
    return tables_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _run_from_repo_root(monkeypatch):
    """Resolve the JSON's repo-relative paths regardless of pytest's launch dir."""
    monkeypatch.chdir(REPO_ROOT)


class TestCommandJson:

    def test_nearest_pcraster_output(self):
        """Full run from a JSON file: one PCRaster map per GRIB step, right shape."""
        with tempfile.TemporaryDirectory() as out_dir:
            rc = _run(_json('nearest.json'), out_dir)

            assert rc == 0
            outputs = _pcr_outputs(out_dir)
            assert len(outputs) == N_STEPS

            for out in outputs:
                values = PCRasterReader(out).values
                assert values.shape == TARGET_SHAPE
                # At least some cells must be valid (not all missing value).
                assert np.any(values != PCR_MV)

    def test_nearest_applies_conversion(self):
        """@applyConversion k2c must turn Kelvin into plausible Celsius values."""
        with tempfile.TemporaryDirectory() as out_dir:
            # Same config without conversion...
            assert _run(_json('nearest.json'), out_dir) == 0
            raw = PCRasterReader(_pcr_outputs(out_dir)[0]).values
            raw_valid = raw[raw != PCR_MV]

        with tempfile.TemporaryDirectory() as out_dir:
            # ...and with k2c conversion.
            assert _run(_json('nearest_k2c.json'), out_dir) == 0
            conv = PCRasterReader(_pcr_outputs(out_dir)[0]).values
            conv_valid = conv[conv != PCR_MV]

        # Kelvin values are ~273 higher than the converted Celsius ones.
        assert raw_valid.mean() > 200
        assert -80 < conv_valid.mean() < 60
        assert np.allclose(raw_valid.mean() - conv_valid.mean(), 273.15, atol=1.0)

    def test_nearest_netcdf_output(self):
        """@format netcdf must produce a single NetCDF file with all timesteps."""
        netCDF4 = pytest.importorskip('netCDF4')
        with tempfile.TemporaryDirectory() as out_dir:
            rc = _run(_json('nearest_netcdf.json'), out_dir)

            assert rc == 0
            nc_files = glob.glob(os.path.join(out_dir, '*.nc'))
            assert len(nc_files) == 1

            ds = netCDF4.Dataset(nc_files[0])
            try:
                main_var = max(ds.variables, key=lambda v: ds.variables[v].ndim)
                var = ds.variables[main_var]
                # (time, y, x) with one slice per GRIB step on the target grid.
                assert var.shape[0] == N_STEPS
                assert var.shape[-2:] == TARGET_SHAPE
            finally:
                ds.close()

    def test_nearest_accumulation_aggregation(self):
        """Accumulation aggregation over 24h collapses the 5 steps into fewer maps."""
        with tempfile.TemporaryDirectory() as out_dir:
            rc = _run(_json('nearest_accumulation.json'), out_dir)

            assert rc == 0
            outputs = _pcr_outputs(out_dir)
            # Aggregating to 24h windows yields fewer maps than the 5 raw steps.
            assert 0 < len(outputs) < N_STEPS
            for out in outputs:
                assert PCRasterReader(out).values.shape == TARGET_SHAPE

    def test_missing_command_file_returns_error(self):
        """pyg2p_exe reports a non-zero return code for a missing JSON file."""
        with tempfile.TemporaryDirectory() as out_dir:
            cmd = (Command()
                   .with_cmdpath(os.path.join(out_dir, 'does_not_exist.json'))
                   .with_inputfile(INPUT_GRIB)
                   .with_outdir(out_dir)
                   .with_eps(EPS_MEMBER)
                   .with_log_level('ERROR'))
            assert run_command(cmd) == 1

    def test_json_run_is_deterministic(self):
        """Running the very same JSON command file twice yields identical maps."""
        def first_map_values():
            with tempfile.TemporaryDirectory() as out_dir:
                assert _run(_json('nearest_k2c.json'), out_dir) == 0
                return PCRasterReader(_pcr_outputs(out_dir)[0]).values

        assert np.array_equal(first_map_values(), first_map_values(), equal_nan=True)

    @pytest.mark.slow
    def test_invdist_creates_and_uses_intertable(self, monkeypatch):
        """invdist from a JSON file; the intertable is created inside the temp dir."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tables_dir = _setup_throwaway_config(monkeypatch, tmp_dir)
            out_dir = os.path.join(tmp_dir, 'out')
            os.makedirs(out_dir)

            rc = _run(_json('invdist.json'), out_dir,
                      create_intertable=True, intertable_dir=tables_dir)

            assert rc == 0
            # The intertable must have been generated under the temp dir.
            tables = glob.glob(os.path.join(tables_dir, '*_scipy_invdist.npy.gz'))
            assert len(tables) == 1

            outputs = _pcr_outputs(out_dir)
            assert len(outputs) == N_STEPS
            for out in outputs:
                assert PCRasterReader(out).values.shape == TARGET_SHAPE

    def _run_adw_weights_mode(self, monkeypatch, weights_mode):
        """Run the full ADW JSON pipeline once for a given @weights_mode.

        Reads the committed ``adw_<weights_mode>.json`` command file, confirms it
        carries the expected ``@weights_mode``, runs it, and returns the stacked
        output maps (one per GRIB step). ADW has no committed intertable, so a
        throwaway config dir plus the create-intertable flag are used, exactly like
        ``test_invdist_creates_and_uses_intertable``.
        """
        cmd_file = _json(f'adw_{weights_mode}.json')
        # The committed JSON really carries the expected @weights_mode.
        with open(cmd_file) as f:
            interp = json.load(f)['Execution']['OutMaps']['Interpolation']
        assert interp['@weights_mode'] == weights_mode
        assert interp['@mode'] == 'adw'

        with tempfile.TemporaryDirectory() as tmp_dir:
            tables_dir = _setup_throwaway_config(monkeypatch, tmp_dir)
            out_dir = os.path.join(tmp_dir, 'out')
            os.makedirs(out_dir)

            rc = _run(cmd_file, out_dir,
                      create_intertable=True, intertable_dir=tables_dir)

            assert rc == 0
            tables = glob.glob(os.path.join(tables_dir, '*_scipy_adw.npy.gz'))
            assert len(tables) == 1

            outputs = _pcr_outputs(out_dir)
            assert len(outputs) == N_STEPS
            maps = np.array([PCRasterReader(out).values for out in outputs])
            assert maps.shape[1:] == TARGET_SHAPE
            return maps

    @pytest.mark.slow
    def test_adw_weights_modes_agree(self, monkeypatch):
        """The three @weights_mode values must produce the SAME ADW maps.

        ``@weights_mode`` (serial / broadcasting / parallel) replaced the old
        ``@use_broadcasting`` flag. The three modes are only different ways of
        computing the directional weights and are mathematically equivalent - the
        committed fixtures in tests/data/adw_directional and tests/data/adw_parallel
        pin all three to the same golden values. Those fixtures come from synthetic
        stations on a small grid, so they are not directly comparable to a real
        JSON run over input.grib on the 810x680 target grid. Instead we use that
        same equivalence as the reference here: run the full JSON pipeline once per
        mode (from the committed adw_*.json files) and require the resulting maps to
        match.

        Tolerance note: the golden ADW tests compare float64 arrays straight from
        ScipyInterpolation and can use RTOL=1e-9. Here the values have been written
        to and read back from PCRaster maps, which are single precision, so the
        comparison is done at float32 level (the three modes still agree to within
        a handful of float32 ulps).
        """
        # PCRaster maps are float32; compare at single-precision tolerance.
        rtol, atol = 1e-5, 1e-4

        serial = self._run_adw_weights_mode(monkeypatch, 'serial')
        broadcasting = self._run_adw_weights_mode(monkeypatch, 'broadcasting')
        parallel = self._run_adw_weights_mode(monkeypatch, 'parallel')

        # PCRaster missing-value cells are identical across modes; comparing only
        # the valid cells keeps the huge MV sentinel out of the tolerance check.
        valid = serial != PCR_MV
        assert np.any(valid)
        np.testing.assert_allclose(broadcasting[valid], serial[valid],
                                   rtol=rtol, atol=atol)
        np.testing.assert_allclose(parallel[valid], serial[valid],
                                   rtol=rtol, atol=atol)
        # Missing-value masks must also line up across modes.
        np.testing.assert_array_equal(broadcasting == PCR_MV, serial == PCR_MV)
        np.testing.assert_array_equal(parallel == PCR_MV, serial == PCR_MV)

    @pytest.mark.slow
    def test_invalid_weights_mode_rejected(self, monkeypatch):
        """An unsupported @weights_mode makes the JSON-driven run fail cleanly."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tables_dir = _setup_throwaway_config(monkeypatch, tmp_dir)
            out_dir = os.path.join(tmp_dir, 'out')
            os.makedirs(out_dir)

            rc = _run(_json('adw_invalid_weights_mode.json'), out_dir,
                      create_intertable=True, intertable_dir=tables_dir)

            assert rc == 1
