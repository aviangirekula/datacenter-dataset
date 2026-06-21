"""Building-footprint enrichment from OSM geometry.

Computes a real ``size_sqft`` (building ground-footprint area) for OSM facilities
mapped as closed ways, using a geodesic area calculation. Optionally derives a
**rough, explicitly-flagged** MW estimate from that footprint.

IMPORTANT — honesty: ``size_sqft`` here is the building *footprint* (ground area
of a single outline), not gross floor area or IT white-space. The MW estimate is
a crude modeled placeholder (footprint × an assumed power density), NOT measured
power — it is flagged per record and should be replaced by a licensed source.
"""
from __future__ import annotations

import json
from pathlib import Path

import requests
from pyproj import Geod
from shapely.geometry import Polygon

from dcdata.schema import AreaBasis, Facility, PowerBasis

_GEOD = Geod(ellps="WGS84")
SQM_TO_SQFT = 10.76391

# Rough whole-building power density for the MODELED MW estimate (not measured).
WATTS_PER_SQFT = 100.0

# Above this footprint, an OSM "data_center" polygon is almost certainly a
# site/campus/landuse boundary rather than a single building (~34 acres). We keep
# its size but flag it and skip the MW estimate (which would be absurd).
MAX_BUILDING_SQFT = 1_500_000.0

USER_AGENT = "gmu-geoai-dc-dataset/0.1 (research)"
GEOM_QUERY = """[out:json][timeout:240];
area["ISO3166-1"="US"][admin_level=2]->.us;
(
  nwr["telecom"="data_center"](area.us);
  nwr["man_made"="data_center"](area.us);
  nwr["building"="data_center"](area.us);
);
out geom;"""


def ensure_geom_file(path: str | Path, overpass_url: str = "https://overpass-api.de/api/interpreter") -> Path:
    """Return the OSM 'out geom' cache path, fetching it once if missing."""
    path = Path(path)
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.post(
        overpass_url,
        data={"data": GEOM_QUERY},
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=260,
    )
    resp.raise_for_status()
    path.write_text(resp.text)
    return path


def footprint_areas(geom_path: str | Path) -> dict[str, float]:
    """Return {osm_ref ('way/123'): footprint_sqft} from an 'out geom' response."""
    data = json.loads(Path(geom_path).read_text())
    areas: dict[str, float] = {}
    for el in data.get("elements", []):
        geom = el.get("geometry")
        if el.get("type") != "way" or not geom or len(geom) < 4:
            continue
        ring = [(p["lon"], p["lat"]) for p in geom]
        if ring[0] != ring[-1]:
            continue  # not a closed ring -> not an area
        try:
            area_m2, _ = _GEOD.geometry_area_perimeter(Polygon(ring))
        except Exception:
            continue
        sqft = abs(area_m2) * SQM_TO_SQFT
        if sqft > 0:
            areas[f"way/{el['id']}"] = round(sqft, 1)
    return areas


def estimate_power_mw(sqft: float) -> float:
    """ROUGH modeled MW estimate from footprint sqft (placeholder, not measured)."""
    return round(sqft * WATTS_PER_SQFT / 1_000_000.0, 2)


def attach_footprint_size(
    facilities: list[Facility], geom_path: str | Path, estimate_power: bool = True
) -> dict:
    """Fill ``size_sqft`` (and an optional flagged MW estimate) on OSM facilities.

    Matches facilities to footprints by their OpenStreetMap ``source_record_id``.
    """
    areas = footprint_areas(geom_path)
    n_size = n_mw = n_big = 0
    note = "power_capacity_mw is a ROUGH ESTIMATE from building footprint (modeled, not measured)."
    for f in facilities:
        ref = next(
            (
                s.source_record_id
                for s in f.sources
                if s.source_name == "OpenStreetMap" and s.source_record_id in areas
            ),
            None,
        )
        if not ref:
            continue
        f.size_sqft = areas[ref]
        n_size += 1
        if areas[ref] > MAX_BUILDING_SQFT:
            # Likely a site/campus boundary, not a building — keep size, flag, no MW.
            f.area_basis = AreaBasis.unknown
            big = "Large footprint — likely a site/campus boundary, not a single building; MW not estimated."
            f.notes = (f.notes + " " + big) if f.notes else big
            n_big += 1
            continue
        f.area_basis = AreaBasis.gross_building
        if estimate_power and f.power_capacity_mw is None:
            f.power_capacity_mw = estimate_power_mw(areas[ref])
            f.power_basis = PowerBasis.unknown
            f.notes = (f.notes + " " + note) if f.notes else note
            n_mw += 1
    return {"footprint_size_filled": n_size, "estimated_mw_filled": n_mw, "oversized_footprints_flagged": n_big}
