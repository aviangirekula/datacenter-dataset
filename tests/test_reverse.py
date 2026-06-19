from datetime import date

import geopandas as gpd
from shapely.geometry import Point, Polygon

from dcdata.geocode.reverse import STATEFP_TO_USPS, TigerReverseGeocoder
from dcdata.schema import Confidence, Facility, FacilitySource


def _f(lat, lon, state=None):
    return Facility(
        facility_id="x",
        latitude=lat,
        longitude=lon,
        state=state,
        confidence=Confidence.medium,
        sources=[FacilitySource(source_name="OSM", date_accessed=date(2026, 6, 18))],
    )


def _fake_counties():
    # One square county covering (-77.6..-77.4, 38.8..39.1), STATEFP 51 (VA).
    poly = Polygon([(-77.6, 38.8), (-77.4, 38.8), (-77.4, 39.1), (-77.6, 39.1)])
    return gpd.GeoDataFrame(
        {"STATEFP": ["51"], "NAME": ["Fairfax"], "GEOID": ["51059"]},
        geometry=[poly],
        crs="EPSG:4326",
    )


def test_statefp_mapping_covers_states_and_territories():
    assert STATEFP_TO_USPS["51"] == "VA"
    assert STATEFP_TO_USPS["06"] == "CA"
    assert STATEFP_TO_USPS["72"] == "PR"


def test_assign_fills_state_and_county():
    facs = [_f(39.0, -77.5)]
    stats = TigerReverseGeocoder().assign(facs, counties=_fake_counties())
    assert facs[0].state == "VA"
    assert facs[0].county == "Fairfax"
    assert stats["reverse_geocoded_state"] == 1
    assert stats["reverse_geocoded_county"] == 1


def test_assign_flags_conflict_with_source_state():
    facs = [_f(39.0, -77.5, state="MD")]  # source said MD; geometry says VA
    stats = TigerReverseGeocoder().assign(facs, counties=_fake_counties())
    assert facs[0].state == "VA"  # geometry is authoritative
    assert stats["admin_conflicts_with_source"] == 1


def test_assign_counts_points_outside_any_county():
    facs = [_f(10.0, 10.0)]  # nowhere near the fake county
    stats = TigerReverseGeocoder().assign(facs, counties=_fake_counties())
    assert stats["points_outside_any_county"] == 1
    assert facs[0].state is None
