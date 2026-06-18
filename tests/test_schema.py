from datetime import date

import pytest

from dcdata.schema import Facility, FacilitySource, make_facility_id
from dcdata.validate.checks import in_conus, looks_lat_lon_swapped, power_in_range


def test_make_facility_id_is_stable():
    """Normalization + coord rounding collapse trivial differences to one ID."""
    a = make_facility_id("Ashburn DC1", 39.0, -77.5)
    b = make_facility_id("ashburn dc1", 39.000004, -77.499996)
    assert a == b


def test_facility_rejects_bad_latitude():
    with pytest.raises(ValueError):
        Facility(facility_id="x", latitude=200.0, longitude=-77.0)


def test_state_is_uppercased():
    f = Facility(facility_id="x", latitude=39.0, longitude=-77.0, state="va")
    assert f.state == "VA"


def test_in_conus_excludes_alaska():
    assert in_conus(38.9, -77.0, "VA") is True
    assert in_conus(64.84, -147.72, "AK") is False  # Fairbanks


def test_lat_lon_swap_heuristic():
    assert looks_lat_lon_swapped(-77.0, 39.0) is True
    assert looks_lat_lon_swapped(39.0, -77.0) is False


def test_power_in_range():
    assert power_in_range(150.0) is True
    assert power_in_range(5000.0) is False


def test_facility_source_roundtrip():
    s = FacilitySource(source_name="OpenStreetMap", date_accessed=date(2026, 6, 18))
    f = Facility(facility_id="dc_1", latitude=39.0, longitude=-77.0, sources=[s])
    assert f.sources[0].source_name == "OpenStreetMap"
