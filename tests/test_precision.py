"""Tests for coordinate_precision, num_floors, manual curation, and merge prefs."""
from datetime import date

from dcdata.collectors.manual import ManualCurationCollector
from dcdata.collectors.osm import OSMCollector
from dcdata.collectors.peeringdb import PeeringDBCollector
from dcdata.resolve.dedup import resolve_entities
from dcdata.schema import Confidence, CoordinatePrecision, Facility, FacilitySource, Status


def test_osm_sets_building_precision_and_floors():
    el = {
        "type": "way",
        "id": 1,
        "center": {"lat": 39.0, "lon": -77.5},
        "tags": {"name": "DC", "telecom": "data_center", "building:levels": "3"},
    }
    f = OSMCollector({"cache": "/none.json"})._to_facility(el, date(2026, 6, 20))
    assert f.coordinate_precision == CoordinatePrecision.building
    assert f.num_floors == 3


def test_peeringdb_sets_geocoded_address_precision():
    rec = {"id": 1, "name": "X", "latitude": 39.0, "longitude": -77.0}
    f = PeeringDBCollector({"cache": "/none.json"})._to_facility(rec, date(2026, 6, 20))
    assert f.coordinate_precision == CoordinatePrecision.geocoded_address


def test_merge_prefers_building_specific_coordinate():
    # Same site: one geocoded-address point, one building point ~10 m away.
    geocoded = Facility(
        facility_id="a", name="Equinix Ashburn", latitude=39.0, longitude=-77.5,
        coordinate_precision=CoordinatePrecision.geocoded_address, confidence=Confidence.medium,
        sources=[FacilitySource(source_name="PeeringDB", source_record_id="1", date_accessed=date(2026, 6, 20))],
    )
    building = Facility(
        facility_id="b", name="Equinix Ashburn", latitude=39.00008, longitude=-77.5,
        coordinate_precision=CoordinatePrecision.building, confidence=Confidence.medium,
        sources=[FacilitySource(source_name="OpenStreetMap", source_record_id="way/9", date_accessed=date(2026, 6, 20))],
    )
    merged, _ = resolve_entities([geocoded, building])
    assert len(merged) == 1
    assert merged[0].coordinate_precision == CoordinatePrecision.building
    assert merged[0].latitude == building.latitude  # kept the building coordinate


def test_manual_curation_row(tmp_path):
    csv_path = tmp_path / "curated.csv"
    csv_path.write_text(
        "name,latitude,longitude,num_floors,status,compute_capabilities,source_url,confidence\n"
        "__EXAMPLE__,1,1,1,operational,,,high\n"
        "Acme AI DC,39.1,-77.2,4,under_construction,AI/GPU,https://news.example/x,high\n"
    )
    facs = list(ManualCurationCollector({"path": str(csv_path)}).collect())
    assert len(facs) == 1  # example row skipped
    f = facs[0]
    assert f.name == "Acme AI DC"
    assert f.num_floors == 4
    assert f.status == Status.under_construction
    assert f.compute_capabilities == "AI/GPU"
    assert f.coordinate_precision == CoordinatePrecision.building  # default for curated
    assert f.sources[0].source_url == "https://news.example/x"
