import json
from datetime import date

from dcdata.enrich.footprint import (
    attach_footprint_size,
    estimate_power_mw,
    footprint_areas,
)
from dcdata.schema import AreaBasis, Facility, FacilitySource

# A ~small closed square near lat 39 (≈86 m × 111 m ≈ 9,600 m² ≈ 103k sqft).
_SQUARE = {
    "elements": [
        {
            "type": "way",
            "id": 5,
            "geometry": [
                {"lon": -77.0, "lat": 39.0},
                {"lon": -76.999, "lat": 39.0},
                {"lon": -76.999, "lat": 39.001},
                {"lon": -77.0, "lat": 39.001},
                {"lon": -77.0, "lat": 39.0},
            ],
        }
    ]
}


def test_footprint_area_plausible(tmp_path):
    p = tmp_path / "geom.json"
    p.write_text(json.dumps(_SQUARE))
    areas = footprint_areas(p)
    assert "way/5" in areas
    assert 80_000 < areas["way/5"] < 130_000  # ~103k sqft


def test_estimate_power_mw_math():
    assert estimate_power_mw(1_000_000) == 100.0  # 1e6 sqft × 100 W/sqft = 100 MW


def _osm_facility(num_floors=None):
    return Facility(
        facility_id="x",
        latitude=39.0005,
        longitude=-76.9995,
        num_floors=num_floors,
        sources=[FacilitySource(
            source_name="OpenStreetMap", source_record_id="way/5", date_accessed=date(2026, 6, 20)
        )],
    )


def test_attach_size_and_flagged_estimate(tmp_path):
    p = tmp_path / "geom.json"
    p.write_text(json.dumps(_SQUARE))
    f = _osm_facility()
    stats = attach_footprint_size([f], p)
    assert f.size_sqft and f.size_sqft > 0
    assert f.area_basis == AreaBasis.gross_building
    assert f.power_demand_mw is not None        # modeled energy goes to power_demand_mw
    assert f.power_capacity_mw is None          # capacity reserved for measured source
    assert "modeled" in (f.notes or "").lower()  # flagged
    assert stats["footprint_size_filled"] == 1


def test_energy_scales_with_floors(tmp_path):
    p = tmp_path / "geom.json"
    p.write_text(json.dumps(_SQUARE))
    one, three = _osm_facility(num_floors=1), _osm_facility(num_floors=3)
    attach_footprint_size([one], p)
    attach_footprint_size([three], p)
    assert round(three.power_demand_mw, 3) == round(one.power_demand_mw * 3, 3)
