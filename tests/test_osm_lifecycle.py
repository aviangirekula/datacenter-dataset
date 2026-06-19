from datetime import date

from dcdata.collectors.osm_lifecycle import OSMLifecycleCollector
from dcdata.schema import GeocodePrecision, Status


def _collector():
    return OSMLifecycleCollector({"cache": "/nonexistent_lifecycle.json"})


def test_construction_tag_is_under_construction():
    el = {
        "type": "way",
        "id": 1,
        "center": {"lat": 39.0, "lon": -77.5},
        "tags": {"name": "AWS IAD-500", "construction": "data_center"},
    }
    f = _collector()._to_facility(el, date(2026, 6, 18))
    assert f.status == Status.under_construction
    assert f.geocode_precision == GeocodePrecision.parcel


def test_proposed_tag_is_planned():
    el = {
        "type": "node",
        "id": 2,
        "lat": 45.5,
        "lon": -122.9,
        "tags": {"name": "QTS Hillsboro 3", "proposed:telecom": "data_center"},
    }
    f = _collector()._to_facility(el, date(2026, 6, 18))
    assert f.status == Status.planned


def test_base_osm_collector_still_operational():
    from dcdata.collectors.osm import OSMCollector

    el = {"type": "node", "id": 3, "lat": 39.0, "lon": -77.0, "tags": {"name": "X DC"}}
    f = OSMCollector({"cache": "/nonexistent.json"})._to_facility(el, date(2026, 6, 18))
    assert f.status == Status.operational
