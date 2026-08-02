"""Turn the cached building and flood responses into per-facility attributes.

Reads the JSONL caches written by ``fetch_building_attributes.py`` and produces
``data/processed/building_attributes.csv`` plus a coverage report.

Building selection, in priority order:
1. A building polygon that **contains** the facility coordinate. If several do
   (overlapping footprints), the largest is taken.
2. Otherwise the **nearest** building within ``NEAR_M``, recorded as such.
3. Otherwise no match, recorded as a miss.

``building_match`` distinguishes these, so any downstream analysis can require
the strong condition rather than silently accepting a neighbour's building.

Storeys are NOT inferred from height by a hidden rule. ``height_m`` is reported
as measured, and a single documented threshold splits low-rise from multi-storey
so the assumption is visible and changeable in one place.

    ./.venv/bin/python scripts/build_building_attributes.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Geod
from shapely.geometry import Point, Polygon

REPO = Path(__file__).resolve().parents[1]
DC_CSV = REPO / "data" / "processed" / "datacenters_final.csv"
STRUCT = REPO / "data" / "raw" / "buildings" / "usa_structures.jsonl"
FLOOD = REPO / "data" / "raw" / "buildings" / "fema_flood_zones.jsonl"
OUT = REPO / "data" / "processed" / "building_attributes.csv"
OUT_JSON = REPO / "data" / "processed" / "building_attributes_coverage.json"

GEOD = Geod(ellps="WGS84")
NEAR_M = 200.0
# Height at or above which a structure is treated as multi-storey. Data halls
# have tall clear heights, so a domestic two-storey threshold would misclassify
# single-storey data centers. Stated here so it can be revised in one place and
# reported in the methods.
MULTI_STOREY_M = 12.0

# FEMA zones beginning with A or V are Special Flood Hazard Areas (the
# regulatory 1%-annual-chance floodplain). X is outside it. D is undetermined.
SFHA_PREFIXES = ("A", "V")


def _poly(feat) -> Polygon | None:
    rings = (feat.get("geometry") or {}).get("rings") or []
    if not rings or len(rings[0]) < 4:
        return None
    try:
        p = Polygon(rings[0])
        return p if p.is_valid else p.buffer(0)
    except Exception:  # noqa: BLE001
        return None


def _area_sqft(poly: Polygon) -> float:
    lon, lat = poly.exterior.coords.xy
    area_m2, _ = GEOD.polygon_area_perimeter(list(lon), list(lat))
    return abs(area_m2) * 10.76391


def _dist_m(lon1, lat1, lon2, lat2) -> float:
    _, _, d = GEOD.inv(lon1, lat1, lon2, lat2)
    return d


def load_structures() -> dict:
    out = {}
    if not STRUCT.exists():
        return out
    with open(STRUCT) as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            fid, lon, lat = r["facility_id"], r["lon"], r["lat"]
            pt = Point(lon, lat)
            best, best_kind, best_dist = None, "none", np.nan
            containing, nearest, nd = [], None, np.inf

            for f in r.get("features", []):
                poly = _poly(f)
                if poly is None:
                    continue
                a = f["attributes"]
                if poly.contains(pt):
                    containing.append((poly, a))
                else:
                    c = poly.centroid
                    d = _dist_m(lon, lat, c.x, c.y)
                    if d < nd:
                        nd, nearest = d, (poly, a)

            if containing:
                poly, a = max(containing, key=lambda t: _area_sqft(t[0]))
                best, best_kind, best_dist = (poly, a), "contains", 0.0
            elif nearest is not None and nd <= NEAR_M:
                best, best_kind, best_dist = nearest, "nearest", nd

            rec = {"building_match": best_kind,
                   "building_dist_m": best_dist,
                   "n_buildings_200m": len(r.get("features", []))}
            if best is not None:
                poly, a = best
                h = a.get("HEIGHT")
                rec.update({
                    "build_id": a.get("BUILD_ID"),
                    "footprint_sqft": round(_area_sqft(poly), 1),
                    "source_sqft": a.get("SQFEET"),
                    "height_m": float(h) if h not in (None, "") else np.nan,
                    "occupancy_class": a.get("OCC_CLS"),
                    "building_address": a.get("PROP_ADDR"),
                    "imagery_date": a.get("IMAGE_DATE"),
                })
            out[fid] = rec
    return out


def load_flood() -> dict:
    out = {}
    if not FLOOD.exists():
        return out
    with open(FLOOD) as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            feats = r.get("features", [])
            if not feats:
                # No polygon here means the location is outside FEMA's mapped
                # extent, which is NOT the same as "no flood risk".
                out[r["facility_id"]] = {"flood_zone": None, "flood_mapped": False,
                                         "flood_sfha": np.nan}
                continue
            zones = [f["attributes"].get("FLD_ZONE") for f in feats]
            zones = [z for z in zones if z]
            # Most hazardous wins if a point sits on a boundary.
            sfha = any(str(z).upper().startswith(SFHA_PREFIXES) for z in zones)
            pick = next((z for z in zones
                         if str(z).upper().startswith(SFHA_PREFIXES)), zones[0] if zones else None)
            out[r["facility_id"]] = {
                "flood_zone": pick,
                "flood_mapped": True,
                "flood_sfha": bool(sfha),
                "flood_subtype": feats[0]["attributes"].get("ZONE_SUBTY"),
            }
    return out


def main() -> None:
    dc = pd.read_csv(DC_CSV, low_memory=False)
    S, F = load_structures(), load_flood()
    print(f"facilities: {len(dc)} | structure records: {len(S)} | flood records: {len(F)}")

    rows = []
    for r in dc.itertuples():
        fid = str(r.facility_id)
        rec = {"facility_id": fid, "name": r.name, "state": r.state,
               "latitude": r.latitude, "longitude": r.longitude}
        rec.update(S.get(fid, {"building_match": "not_fetched"}))
        rec.update(F.get(fid, {"flood_zone": None, "flood_mapped": None}))
        rows.append(rec)
    out = pd.DataFrame(rows)

    if "height_m" in out:
        out["multi_storey"] = np.where(
            out["height_m"].notna(), out["height_m"] >= MULTI_STOREY_M, None)

    n = len(out)
    mm = out["building_match"].value_counts(dropna=False).to_dict()
    cov = {
        "n_facilities": n,
        "building_match": {str(k): int(v) for k, v in mm.items()},
        "height_measured": int(out["height_m"].notna().sum()) if "height_m" in out else 0,
        "height_threshold_m": MULTI_STOREY_M,
        "flood_mapped": int((out["flood_mapped"] == True).sum()),  # noqa: E712
        "flood_in_sfha": int((out["flood_sfha"] == True).sum()),   # noqa: E712
        "search_radius_m": NEAR_M,
    }
    print("\n=== coverage ===")
    print("building match:", cov["building_match"])
    print(f"height measured: {cov['height_measured']}/{n} "
          f"({100*cov['height_measured']/n:.1f}%)")
    print(f"flood mapped   : {cov['flood_mapped']}/{n}")
    print(f"in SFHA (1% floodplain): {cov['flood_in_sfha']}")
    if "flood_zone" in out:
        print("\ntop flood zones:")
        print(out["flood_zone"].value_counts(dropna=False).head(8).to_string())

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    OUT_JSON.write_text(json.dumps(cov, indent=2) + "\n")
    print(f"\nWrote {OUT.relative_to(REPO)} ({len(out)} rows, {len(out.columns)} cols)")


if __name__ == "__main__":
    main()
