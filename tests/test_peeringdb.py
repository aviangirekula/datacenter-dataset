from datetime import date

from dcdata.collectors.peeringdb import PeeringDBCollector
from dcdata.schema import FacilityType, GeocodePrecision, Status


def _collector():
    return PeeringDBCollector({"cache": "/nonexistent_pdb.json"})


def test_parse_facility_with_coords():
    rec = {
        "id": 1,
        "name": "Equinix DC1-DC15 - Ashburn",
        "city": "Ashburn",
        "state": "VA",
        "zipcode": "20147",
        "address1": "21715 Filigree Ct",
        "latitude": 39.0163,
        "longitude": -77.459,
    }
    f = _collector()._to_facility(rec, date(2026, 6, 20))
    assert f.facility_type == FacilityType.colocation  # "Equinix" matched in name
    assert f.status == Status.operational
    assert f.geocode_precision == GeocodePrecision.address
    assert f.city == "Ashburn"
    assert f.sources[0].source_url.endswith("/fac/1")


def test_skips_facility_without_coords():
    rec = {"id": 2, "name": "No Coords Facility", "latitude": None, "longitude": None}
    assert _collector()._to_facility(rec, date(2026, 6, 20)) is None
