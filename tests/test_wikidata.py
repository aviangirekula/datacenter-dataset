from datetime import date

from dcdata.collectors.wikidata import WikidataCollector
from dcdata.schema import Confidence, FacilityType


def _collector():
    return WikidataCollector({"cache": "/nonexistent_wd.json"})


def test_parse_point_lon_lat_order():
    # WKT is Point(lon lat); we return (lat, lon)
    assert WikidataCollector.parse_point("Point(-77.459 39.016)") == (39.016, -77.459)
    assert WikidataCollector.parse_point("not a point") is None


def test_to_facility_from_binding():
    b = {
        "dc": {"value": "http://www.wikidata.org/entity/Q123"},
        "dcLabel": {"value": "Hyperion"},
        "coord": {"value": "Point(-91.632333 32.477149)"},
        "operatorLabel": {"value": "Meta"},
    }
    f = _collector()._to_facility(b, date(2026, 6, 20))
    assert f.operator_company == "Meta"
    assert f.facility_type == FacilityType.hyperscale
    assert f.coord_confidence == Confidence.low  # Wikidata coords are low-confidence
    assert f.sources[0].source_url.endswith("/Q123")
