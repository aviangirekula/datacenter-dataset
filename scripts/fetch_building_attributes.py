"""Fetch building footprints, heights and FEMA flood zones per facility.

Two public ArcGIS services are queried once per facility and cached to disk as
JSONL so the run is resumable and re-runnable without re-hitting the services:

- **USA Structures** (ORNL / FEMA / NGA): building polygons with footprint area,
  occupancy class and, where available, HEIGHT in metres. Supplies the building
  geometry needed for footprint-based hazard sampling and the storey control.
- **FEMA National Flood Hazard Layer**, layer 28 "Flood Hazard Zones": the
  regulatory flood zone polygon a facility falls in.

Honesty rules, same as the hazard sampler:
- A facility with no building match is recorded as a miss, never invented.
- ``inside`` records whether the coordinate falls *within* a building polygon
  versus merely near one, so downstream code can require the stronger condition.
- HEIGHT coverage is regionally patchy in the source. Coverage is measured and
  reported, never assumed.

    ./.venv/bin/python scripts/fetch_building_attributes.py            # resume
    ./.venv/bin/python scripts/fetch_building_attributes.py --limit 50 # smoke test
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
DC_CSV = REPO / "data" / "processed" / "datacenters_final.csv"
CACHE = REPO / "data" / "raw" / "buildings"
def struct_cache(radius_m: float) -> Path:
    """Cache path keyed by radius. Keying on facility_id alone would
    silently reuse a narrower search when the radius is widened."""
    return CACHE / f"usa_structures_r{int(radius_m)}.jsonl"


STRUCT_JSONL = CACHE / "usa_structures.jsonl"  # legacy 200 m cache
FLOOD_JSONL = CACHE / "fema_flood_zones.jsonl"

STRUCT_URL = ("https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/"
              "USA_Structures_View/FeatureServer/0/query")
FLOOD_URL = ("https://hazards.fema.gov/arcgis/rest/services/public/NFHL/"
             "MapServer/28/query")

# Search radius around each facility. Large enough to catch a campus building
# whose centroid the coordinate misses, small enough not to grab a neighbour.
SEARCH_M = 200
UA = {"User-Agent": "datacenter-dataset/0.1 (academic research; GMU GeoAI)"}
WORKERS = 6
RETRIES = 3


def _get(url: str, params: dict) -> dict:
    q = urllib.parse.urlencode({**params, "f": "json"})
    last = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(f"{url}?{q}", headers=UA)
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf8"))
        except Exception as e:  # noqa: BLE001 - network flakiness is expected
            last = e
            time.sleep(1.5 * (attempt + 1))
    return {"error": {"message": f"{type(last).__name__}: {last}"}}


def fetch_structure(fid: str, lon: float, lat: float,
                    radius_m: float = SEARCH_M) -> dict:
    res = _get(STRUCT_URL, {
        "geometry": json.dumps({"x": lon, "y": lat,
                                "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryPoint", "inSR": "4326",
        "distance": str(radius_m), "units": "esriSRUnit_Meter",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "BUILD_ID,OCC_CLS,PRIM_OCC,PROP_ADDR,HEIGHT,SQFEET,SQMETERS,IMAGE_DATE",
        "returnGeometry": "true", "outSR": "4326",
    })
    return {"facility_id": fid, "lon": lon, "lat": lat, "radius_m": radius_m,
            "exceeded_limit": bool(res.get("exceededTransferLimit")),
            "error": res.get("error"), "features": res.get("features", [])}


def fetch_flood(fid: str, lon: float, lat: float) -> dict:
    res = _get(FLOOD_URL, {
        "geometry": json.dumps({"x": lon, "y": lat,
                                "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryPoint", "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE,DEPTH",
        "returnGeometry": "false",
    })
    return {"facility_id": fid, "error": res.get("error"),
            "features": res.get("features", [])}


def _done(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids = set()
    with open(path) as fh:
        for line in fh:
            try:
                ids.add(json.loads(line)["facility_id"])
            except Exception:  # noqa: BLE001 - tolerate a torn final line
                continue
    return ids


def run(kind: str, fn, path: Path, rows) -> None:
    done = _done(path)
    todo = [r for r in rows if r[0] not in done]
    print(f"{kind}: {len(done)} cached, {len(todo)} to fetch")
    if not todo:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    n_err = 0
    with open(path, "a") as out, ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for i, rec in enumerate(ex.map(lambda r: fn(*r), todo), 1):
            if rec.get("error"):
                n_err += 1
            out.write(json.dumps(rec) + "\n")
            if i % 200 == 0:
                out.flush()
                print(f"  {kind}: {i}/{len(todo)}  errors={n_err}")
    print(f"{kind}: done, {n_err} errors")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="smoke-test N facilities")
    ap.add_argument("--only", choices=["structures", "flood"], help="one source only")
    ap.add_argument("--radius", type=float, default=SEARCH_M,
                    help="search radius in metres (cache is keyed by it)")
    ap.add_argument("--ids-file", help="restrict to facility_ids listed one per line")
    args = ap.parse_args()

    dc = pd.read_csv(DC_CSV, low_memory=False)
    rows = [(str(r.facility_id), float(r.longitude), float(r.latitude))
            for r in dc.itertuples()]
    if args.ids_file:
        keep = {line.strip() for line in open(args.ids_file) if line.strip()}
        rows = [r for r in rows if r[0] in keep]
    if args.limit:
        rows = rows[: args.limit]
    print(f"facilities: {len(rows)}  radius: {args.radius:.0f} m")

    if args.only != "flood":
        path = (STRUCT_JSONL if args.radius == SEARCH_M
                else struct_cache(args.radius))
        run("structures", lambda f, lo, la: fetch_structure(f, lo, la, args.radius),
            path, rows)
    if args.only != "structures":
        run("flood", fetch_flood, FLOOD_JSONL, rows)


if __name__ == "__main__":
    main()
