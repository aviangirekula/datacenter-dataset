from datetime import date

from dcdata.classify import classify_facility_type
from dcdata.collectors.osm import OSMCollector
from dcdata.schema import FacilityType, GeocodePrecision, Status


def test_classify_hyperscale():
    assert classify_facility_type("Some DC", "Amazon Web Services") == FacilityType.hyperscale
    assert classify_facility_type(None, "Google") == FacilityType.hyperscale


def test_classify_colocation():
    assert classify_facility_type("Equinix DC1", "Equinix") == FacilityType.colocation
    assert classify_facility_type(None, "Digital Realty") == FacilityType.colocation


def test_classify_excluded_minor():
    assert classify_facility_type("SDSU Computer Room", None) == FacilityType.excluded_minor
    assert classify_facility_type("The Pittock Internet Exchange", None) == FacilityType.excluded_minor


def test_classify_unknown_stays_included():
    assert classify_facility_type("Acme Data Center", "Acme Holdings") == FacilityType.unknown


def _collector():
    return OSMCollector({"cache": "/nonexistent_cache_for_test.json"})


def test_parse_way_centroid_is_parcel_precision():
    el = {
        "type": "way",
        "id": 123,
        "center": {"lat": 39.0, "lon": -77.5},
        "tags": {"name": "Ashburn DC", "operator": "Google", "telecom": "data_center"},
    }
    f = _collector()._to_facility(el, date(2026, 6, 18))
    assert f.facility_type == FacilityType.hyperscale
    assert f.status == Status.operational
    assert f.geocode_precision == GeocodePrecision.parcel
    assert f.sources[0].source_url.endswith("way/123")
    assert f.included is True


def test_parse_node_is_address_precision():
    el = {
        "type": "node",
        "id": 9,
        "lat": 38.9,
        "lon": -77.0,
        "tags": {"name": "Server Room A"},
    }
    f = _collector()._to_facility(el, date(2026, 6, 18))
    assert f.geocode_precision == GeocodePrecision.address
    assert f.facility_type == FacilityType.excluded_minor  # "server room"
    assert f.included is False
