"""Invariants on the published hazard-exposure table.

These guard the artifact a paper would cite. They are skipped when the table has
not been generated (raw hazard layers are gitignored), so a fresh clone still
runs green.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
CSV = REPO / "data" / "processed" / "hazard_exposure.csv"
FACILITIES = REPO / "data" / "processed" / "datacenters_final.csv"

pytestmark = pytest.mark.skipif(
    not CSV.exists(), reason="hazard_exposure.csv not built in this checkout"
)


@pytest.fixture(scope="module")
def haz() -> pd.DataFrame:
    return pd.read_csv(CSV, low_memory=False)


def test_one_row_per_facility(haz):
    assert not haz["facility_id"].duplicated().any()
    if FACILITIES.exists():
        fac = pd.read_csv(FACILITIES, low_memory=False)
        assert set(haz["facility_id"]) == set(fac["facility_id"])


def test_wildfire_severity_excludes_nominal_codes(haz):
    """Codes 6 and 7 are nominal surfaces, so severity must be null there.

    Mixing them into the ordinal column would make any mean or ranking invalid.
    """
    code, sev = haz["haz_wildfire_whp_code"], haz["haz_wildfire_whp_severity"]
    nominal = code.isin([6, 7])
    assert sev[nominal].isna().all()
    assert (sev[~nominal & code.notna()] == code[~nominal & code.notna()]).all()
    assert sev.dropna().between(1, 5).all()


def test_water_flag_matches_code_7(haz):
    flag = haz["qa_coordinate_on_water"].astype(bool)
    assert (flag == (haz["haz_wildfire_whp_code"] == 7)).all()


def test_seismic_return_periods_are_monotonic(haz):
    """A rarer event cannot shake less than a more frequent one.

    Catches a layer mix-up between the 2%, 5% and 10% in 50 yr maps.
    """
    a = haz["haz_seismic_pga_g_475yr"]
    b = haz["haz_seismic_pga_g_975yr"]
    c = haz["haz_seismic_pga_g_2475yr"]
    ok = a.notna() & b.notna() & c.notna()
    # Allow one contour band (0.01 g) of discretisation slack.
    assert (b[ok] >= a[ok] - 0.011).all()
    assert (c[ok] >= b[ok] - 0.011).all()


def test_imputation_is_flagged_not_hidden(haz):
    """Every seismic value must be attributable to a sampling method."""
    for rp in (475, 975, 2475):
        val = haz[f"haz_seismic_pga_g_{rp}yr"]
        method = haz[f"haz_seismic_pga_g_{rp}yr_method"]
        assert set(method.unique()) <= {0, 1, 2}
        assert val[method == 0].isna().all(), "method 0 must carry no value"
        assert val[method.isin([1, 2])].notna().all()


def test_burnable_fraction_in_unit_range(haz):
    for r in (1000, 2400, 5000):
        f = haz[f"haz_wildfire_burnable_frac_{r}m"].dropna()
        assert f.between(0, 1).all()


def test_buffer_severity_is_monotonic_in_radius(haz):
    """A larger disc contains the smaller one, so max severity cannot fall."""
    s1 = haz["haz_wildfire_max_severity_1000m"]
    s2 = haz["haz_wildfire_max_severity_2400m"]
    s5 = haz["haz_wildfire_max_severity_5000m"]
    assert (s2.fillna(0) >= s1.fillna(0)).all()
    assert (s5.fillna(0) >= s2.fillna(0)).all()


def test_positional_accuracy_is_carried_through(haz):
    for col in ("coordinate_precision", "verification_status", "coord_confidence"):
        assert col in haz.columns, f"{col} must travel with the hazard values"


def test_no_hazard_column_is_silently_zero_filled(haz):
    """Guards against nodata being written as 0 rather than null."""
    lightning = haz["haz_lightning_flash_per_km2_yr"]
    assert (lightning.dropna() > 0).all(), "flash rate of exactly 0 suggests nodata fill"
