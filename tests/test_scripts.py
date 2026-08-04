"""Unit tests for the pure logic inside ``scripts/``.

The analysis scripts were previously untested: about 2,500 lines whose only
verification was manual review. These tests cover the pure functions, the ones
that decide what a number means, without touching the network or the multi
gigabyte raw layers.

Several of these lock behaviour that adversarial review found broken at least
once, so they are regression tests, not decoration.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load(name: str):
    """Import a script by path. They are entry points, not an installed package."""
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# --- ring parsing and geodesic area -------------------------------------------

@pytest.fixture(scope="module")
def bld():
    return _load("build_building_attributes")


def test_ring_area_sign_encodes_orientation(bld):
    """ArcGIS marks exteriors clockwise and holes counter-clockwise."""
    cw = [(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)]
    ccw = [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]
    assert bld._ring_area(cw) < 0
    assert bld._ring_area(ccw) > 0
    assert abs(bld._ring_area(cw)) == pytest.approx(1.0)


def test_poly_subtracts_a_hole(bld):
    """Using rings[0] alone overstated one real footprint by 45%."""
    outer = [(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)]              # cw, exterior
    hole = [(0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75), (0.25, 0.25)]
    solid = bld._poly({"geometry": {"rings": [outer]}})
    holed = bld._poly({"geometry": {"rings": [outer, hole]}})
    assert holed.area < solid.area
    assert holed.area == pytest.approx(solid.area - 0.25, abs=1e-9)


def test_poly_handles_multipart(bld):
    a = [(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)]
    b = [(5, 5), (5, 6), (6, 6), (6, 5), (5, 5)]
    g = bld._poly({"geometry": {"rings": [a, b]}})
    assert g is not None and g.area == pytest.approx(2.0)


def test_poly_rejects_degenerate(bld):
    assert bld._poly({"geometry": {"rings": []}}) is None
    assert bld._poly({"geometry": {"rings": [[(0, 0), (1, 1)]]}}) is None
    assert bld._poly({}) is None


def test_area_sqft_matches_a_known_square(bld):
    """A 0.001 deg square near 39 N is about 86 m x 111 m."""
    ring = [(-77.0, 39.0), (-77.0, 39.001), (-76.999, 39.001), (-76.999, 39.0),
            (-77.0, 39.0)]
    g = bld._poly({"geometry": {"rings": [ring]}})
    sqft = bld._area_sqft(g)
    assert 80_000 < sqft < 130_000


def test_area_sqft_subtracts_holes_not_just_exterior(bld):
    outer = [(-77.0, 39.0), (-77.0, 39.002), (-76.998, 39.002), (-76.998, 39.0),
             (-77.0, 39.0)]
    hole = [(-76.9995, 39.0005), (-76.9985, 39.0005), (-76.9985, 39.0015),
            (-76.9995, 39.0015), (-76.9995, 39.0005)]
    solid = bld._area_sqft(bld._poly({"geometry": {"rings": [outer]}}))
    holed = bld._area_sqft(bld._poly({"geometry": {"rings": [outer, hole]}}))
    assert holed < solid * 0.95


def test_dist_m_is_geodesic(bld):
    """One degree of latitude is about 111 km anywhere."""
    d = bld._dist_m(-77.0, 39.0, -77.0, 40.0)
    assert 110_000 < d < 112_000


# --- positional sigma assignment ----------------------------------------------

@pytest.fixture(scope="module")
def unc():
    sys.path.insert(0, str(SCRIPTS.parents[0] / "src"))
    return _load("coordinate_uncertainty")


def _frames(precision, match, dist):
    dc = pd.DataFrame({"facility_id": ["a"], "coordinate_precision": [precision]})
    attr = pd.DataFrame({"facility_id": ["a"], "building_match": [match],
                         "building_dist_m": [dist]})
    return dc, attr


def test_geocode_inside_a_building_is_not_promoted_to_10m(unc):
    """Regression: 797 street geocodes were treated as 10 m coordinates simply
    because they happened to fall inside some footprint."""
    dc, attr = _frames("geocoded_address", "contains", 0.0)
    assert unc.assign_sigma(dc, attr)[0] == unc.SIGMA_M["geocoded_address"]


def test_building_precision_inside_a_building_is_10m(unc):
    dc, attr = _frames("building", "contains", 0.0)
    assert unc.assign_sigma(dc, attr)[0] == unc.SIGMA_M["building"]


def test_parcel_tier_requires_the_distance_it_claims(unc):
    """The 30 m tier means 'within a parcel', so a 600 m match cannot earn it."""
    near = unc.assign_sigma(*_frames("building", "nearest", 50.0))[0]
    far = unc.assign_sigma(*_frames("building", "nearest", 600.0))[0]
    assert near == unc.SIGMA_M["verified"]
    assert far >= unc.SIGMA_M["geocoded_address"]


def test_unknown_precision_gets_the_widest_sigma(unc):
    dc, attr = _frames(None, "none", np.nan)
    assert unc.assign_sigma(dc, attr)[0] == unc.SIGMA_M["unknown"]


def test_sigma_tiers_are_ordered(unc):
    m = unc.SIGMA_M
    assert m["building"] < m["verified"] < m["geocoded_address"] < \
        m["campus_centroid"] < m["unknown"]


# --- Poisson intervals ---------------------------------------------------------

@pytest.fixture(scope="module")
def storm():
    return _load("build_storm_exposure")


def test_poisson_ci_brackets_the_estimate(storm):
    k = np.array([0, 1, 5, 50])
    lo, hi = storm.poisson_ci(k, exposure=10.0)
    rate = k / 10.0
    assert (lo <= rate + 1e-12).all()
    assert (hi >= rate - 1e-12).all()


def test_poisson_ci_zero_count_has_zero_lower_and_positive_upper(storm):
    """A facility with no observed events must not be published as a bare 0."""
    lo, hi = storm.poisson_ci(np.array([0]), exposure=25.0)
    assert lo[0] == 0.0
    assert hi[0] > 0.0


def test_poisson_ci_narrows_as_counts_grow(storm):
    lo, hi = storm.poisson_ci(np.array([5, 500]), exposure=1.0)
    assert (hi[0] - lo[0]) / 5 > (hi[1] - lo[1]) / 500


def test_significant_thresholds_match_spc_conventions(storm):
    d = storm.DATASETS
    g = pd.DataFrame({"mag": [-9, 0, 1, 2, 3]})
    assert d["tornado"]["sig"](g).tolist() == [False, False, False, True, True]
    assert d["tornado"]["valid_mag"](g).tolist() == [False, True, True, True, True]
    h = pd.DataFrame({"mag": [0.75, 1.99, 2.0, 3.0]})
    assert d["hail"]["sig"](h).tolist() == [False, False, True, True]
    w = pd.DataFrame({"mag": [0, 50, 64, 65, 80]})
    # mag == 0 is a missing-value sentinel for wind, not a calm observation.
    assert d["wind"]["valid_mag"](w).tolist() == [False, True, True, True, True]
    assert d["wind"]["sig"](w).tolist() == [False, False, False, True, True]


def test_single_analysis_window_for_every_hazard(storm):
    """Mixed denominators biased tornado up 80% and hail/wind down 40%."""
    assert storm.YEARS == storm.YEAR_TO - storm.YEAR_FROM + 1
    assert storm.YEAR_FROM == 2000 and storm.YEAR_TO == 2024


def test_disc_area_matches_the_radius(storm):
    assert storm.DISC_KM2 == pytest.approx(np.pi * 40.0 ** 2, rel=1e-9)


# --- flood classification ------------------------------------------------------

def test_water_stress_categories_keep_arid_distinct():
    ws = _load("build_water_stress")
    assert ws.CAT[-1] == "arid_and_low_water_use"
    assert ws.CAT[4] == "extremely_high"
    # -1 must not be read as "lower than low".
    assert ws.CAT[-1] != ws.CAT[0]


# --- footprint zonal helpers ---------------------------------------------------

def test_footprint_burnable_codes_exclude_nominal_classes():
    fp = _load("build_footprint_hazard")
    assert set(fp.WHP_BURNABLE) == {1, 2, 3, 4, 5}
    assert 6 not in fp.WHP_BURNABLE  # developed
    assert 7 not in fp.WHP_BURNABLE  # open water
