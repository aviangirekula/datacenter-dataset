from datetime import date

from dcdata.resolve.dedup import haversine_m, is_match, name_similarity, resolve_entities
from dcdata.schema import Confidence, Facility, FacilitySource, GeocodePrecision


def _f(fid, lat, lon, name=None, source="OSM", conf=Confidence.medium,
       precision=GeocodePrecision.address, included=True):
    return Facility(
        facility_id=fid,
        name=name,
        latitude=lat,
        longitude=lon,
        confidence=conf,
        coord_confidence=conf,
        geocode_precision=precision,
        included=included,
        sources=[FacilitySource(
            source_name=source, source_url=f"http://x/{fid}",
            source_record_id=fid, date_accessed=date(2026, 6, 18),
        )],
    )


def test_haversine_known_distance():
    d = haversine_m(39.0, -77.0, 39.001, -77.0)  # ~111 m
    assert 100 < d < 120


def test_name_similarity_subset_is_high():
    assert name_similarity("Equinix Ashburn", "Equinix Ashburn DC") >= 90
    assert name_similarity(None, "x") is None


def test_merge_same_site_preserves_all_sources():
    a = _f("a", 39.0000, -77.5000, "Equinix Ashburn", source="OSM")
    b = _f("b", 39.00005, -77.50003, "Equinix Ashburn DC", source="Baxtel")
    merged, log = resolve_entities([a, b])
    assert len(merged) == 1
    assert {s.source_name for s in merged[0].sources} == {"OSM", "Baxtel"}
    assert len(log) == 1
    assert log[0]["n_merged"] == 2


def test_no_merge_when_far_apart():
    a = _f("a", 39.0, -77.5, "X DC")
    b = _f("b", 40.0, -78.5, "X DC")
    merged, _ = resolve_entities([a, b])
    assert len(merged) == 2


def test_no_record_lost_source_count_preserved():
    facs = [_f(str(i), 39.0 + i * 0.5, -77.0, f"DC{i}") for i in range(5)]
    merged, _ = resolve_entities(facs)
    assert sum(len(f.sources) for f in merged) == 5


def test_merge_keeps_higher_precision_coords():
    a = _f("a", 39.0, -77.5, "DC", precision=GeocodePrecision.city)
    b = _f("b", 39.0001, -77.5001, "DC", precision=GeocodePrecision.parcel)
    merged, _ = resolve_entities([a, b])
    assert merged[0].geocode_precision == GeocodePrecision.parcel


def test_missing_name_merges_only_if_close_and_keeps_name():
    a = _f("a", 39.0, -77.5, None)
    b = _f("b", 39.00003, -77.50002, "Some DC")  # ~6 m away
    merged, _ = resolve_entities([a, b])
    assert len(merged) == 1
    assert merged[0].name == "Some DC"


def test_campus_siblings_not_merged():
    # "Portland 2" vs "Portland 3" are distinct buildings ~50 m apart.
    a = _f("a", 45.4762, -122.7761, "Digital Fortress - Portland 2")
    b = _f("b", 45.47576, -122.7761, "Digital Fortress - Portland 3")
    merged, _ = resolve_entities([a, b])
    assert len(merged) == 2


def test_co_located_different_names_not_merged():
    # Two distinct buildings on a campus, ~50 m apart, clearly different names.
    a = _f("a", 39.0000, -77.5000, "Vantage VA11")
    b = _f("b", 39.00040, -77.50000, "Microsoft MWH01")
    merged, _ = resolve_entities([a, b])
    assert len(merged) == 2
