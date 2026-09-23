"""Measure building height from USGS 3DEP lidar point clouds.

Why. USA Structures carries a height for only 1,327 of the 2,696 facilities and
OpenStreetMap adds 17 more, leaving about half the fleet with none. This measures
the remaining buildings directly from the national lidar archive rather than
estimating them from footprint area, which would not be a measurement.

Method. USGS publishes 3DEP as Entwine Point Tiles on S3, one archive per
acquisition project. For each facility we find the covering project, walk the
octree to the nodes overlapping the building footprint, fetch those LAZ tiles,
and take

    height = P90(non-ground returns inside the footprint) - median(ground returns
             within 25 m of it)

**Why P90 and not the maximum.** Validated against the 14 facilities where USA
Structures already supplies a height, the estimators compare as:

    median   median abs error 1.2 m, correlation 0.59
    P75      median abs error 1.1 m, correlation 0.70
    P90      median abs error 1.9 m, correlation 0.97
    P98      median abs error 4.8 m, correlation 0.98

The high percentiles chase overhanging vegetation and rooftop masts, the low ones
collapse on tall buildings. P90 tracks the reference closely across the range.

**Building classification is mostly absent.** Only about one project in eight
classifies buildings (class 6), so this uses all non-ground returns inside the
footprint instead. The footprint is the building outline, so those returns are
predominantly roof.

This never overwrites a USA Structures or OpenStreetMap value. It only fills gaps,
and it records the point counts behind every value so a weak one can be filtered.

    ./.venv/bin/python scripts/fetch_lidar_heights.py --limit 20
    ./.venv/bin/python scripts/fetch_lidar_heights.py
"""
from __future__ import annotations

import argparse
import io
import json
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely import contains_xy
from shapely.geometry import shape
from urllib3.util.retry import Retry

REPO = Path(__file__).resolve().parents[1]
FOOTPRINTS = REPO / "data" / "processed" / "building_footprints.gpkg"
ATTRS = REPO / "data" / "processed" / "building_attributes.csv"
BOUNDARIES = REPO / "data" / "raw" / "lidar" / "3dep_ept_boundaries.geojson"
CACHE = REPO / "data" / "raw" / "lidar" / "lidar_heights.jsonl"
BOUNDARIES_URL = ("https://raw.githubusercontent.com/hobuinc/usgs-lidar/"
                  "master/boundaries/resources.geojson")

GROUND_BUFFER_M = 25
PERCENTILE = 90
MIN_ROOF_PTS = 30
MIN_GROUND_PTS = 5
MAX_NODES = 25          # cap tiles per site, keeps one slow site from stalling
MAX_DEPTH = 12

SESSION = requests.Session()
SESSION.headers["User-Agent"] = (
    "datacenter-dataset/0.1 (academic research; GMU GeoAI)")
# Sustained bulk fetching gets connections reset by the tile host. Retry with
# backoff at the adapter level, and cap the pool so one site cannot open a burst
# of parallel sockets.
_ADAPTER = requests.adapters.HTTPAdapter(
    max_retries=Retry(total=4, backoff_factor=1.5,
                      status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=frozenset(["GET"])),
    pool_connections=4, pool_maxsize=4)
SESSION.mount("https://", _ADAPTER)
PACE_S = 0.4        # deliberate gap between sites, the host throttles without it


def boundaries() -> gpd.GeoDataFrame:
    if not BOUNDARIES.exists():
        BOUNDARIES.parent.mkdir(parents=True, exist_ok=True)
        r = SESSION.get(BOUNDARIES_URL, timeout=180)
        r.raise_for_status()
        BOUNDARIES.write_bytes(r.content)
    feats = json.loads(BOUNDARIES.read_text())["features"]
    return gpd.GeoDataFrame(
        [{"url": f["properties"]["url"], "project": f["properties"]["name"],
          "geometry": shape(f["geometry"])}
         for f in feats if f.get("geometry")], crs="EPSG:4326")


def node_bounds(root, d, x, y, z):
    x0, y0, z0, x1, y1, z1 = root
    sx, sy, sz = (x1 - x0) / 2**d, (y1 - y0) / 2**d, (z1 - z0) / 2**d
    return (x0 + x * sx, y0 + y * sy, z0 + z * sz,
            x0 + (x + 1) * sx, y0 + (y + 1) * sy, z0 + (z + 1) * sz)


def find_nodes(base: str, root, bbox) -> list[str]:
    """Octree keys whose cube overlaps bbox. -1 means load a deeper hierarchy."""
    hier: dict = {}

    def load(key: str) -> None:
        r = SESSION.get(f"{base}/ept-hierarchy/{key}.json", timeout=60)
        if r.ok:
            hier.update(r.json())

    load("0-0-0-0")
    out, stack = [], [(0, 0, 0, 0)]
    while stack:
        d, x, y, z = stack.pop()
        key = f"{d}-{x}-{y}-{z}"
        cnt = hier.get(key)
        if cnt is None:
            continue
        if cnt == -1:
            load(key)
            cnt = hier.get(key, 0)
        nb = node_bounds(root, d, x, y, z)
        if not (nb[0] < bbox[2] and nb[3] > bbox[0]
                and nb[1] < bbox[3] and nb[4] > bbox[1]):
            continue
        if cnt and cnt > 0:
            out.append(key)
        if d < MAX_DEPTH:
            for dx in (0, 1):
                for dy in (0, 1):
                    for dz in (0, 1):
                        stack.append((d + 1, x * 2 + dx, y * 2 + dy, z * 2 + dz))
    return out


def fetch_tile(base: str, key: str):
    """One LAZ tile, retried. A reset here otherwise discards the whole site."""
    import laspy
    last = None
    for attempt in range(3):
        try:
            r = SESSION.get(f"{base}/ept-data/{key}.laz", timeout=180)
            if not r.ok:
                return None
            las = laspy.read(io.BytesIO(r.content))
            return (np.column_stack([las.x, las.y, las.z]),
                    np.asarray(las.classification))
        except Exception as e:  # noqa: BLE001 - transient host resets
            last = e
            time.sleep(2.0 * (attempt + 1))
    raise last


def height_for(url: str, poly_wgs84) -> dict:
    base = url.rsplit("/ept.json", 1)[0]
    meta = SESSION.get(url, timeout=60).json()
    epsg = (meta.get("srs") or {}).get("horizontal")
    if not epsg:
        return {"error": "no horizontal srs"}
    poly = gpd.GeoSeries([poly_wgs84], crs="EPSG:4326").to_crs(f"EPSG:{epsg}").iloc[0]
    buf = poly.buffer(GROUND_BUFFER_M)
    keys = find_nodes(base, meta["bounds"], buf.bounds)
    if not keys:
        return {"error": "no overlapping nodes"}
    xy, cl = [], []
    for k in keys[:MAX_NODES]:
        got = fetch_tile(base, k)
        if got:
            xy.append(got[0])
            cl.append(got[1])
    if not xy:
        return {"error": "no tiles fetched"}
    pts, cls = np.vstack(xy), np.concatenate(cl)
    inside = contains_xy(poly, pts[:, 0], pts[:, 1])
    near = contains_xy(buf, pts[:, 0], pts[:, 1])
    ground = pts[near & (cls == 2), 2]
    if ground.size < MIN_GROUND_PTS:
        return {"error": f"ground points {ground.size}"}
    roof = pts[inside & (cls != 2), 2]
    if roof.size < MIN_ROOF_PTS:
        return {"error": f"roof points {roof.size}"}
    return {
        "height_m": float(np.percentile(roof, PERCENTILE) - np.median(ground)),
        "n_roof": int(roof.size), "n_ground": int(ground.size),
        "n_class6": int((cls[inside] == 6).sum()), "epsg": epsg,
        "error": None,
    }


def done_ids() -> set[str]:
    """Facility ids already measured SUCCESSFULLY.

    Error rows are deliberately not counted as done. Most failures here are
    transient ConnectionErrors from the tile host rather than anything about the
    site, so a re-run must retry them. Counting them as complete silently caps
    coverage at whatever the network happened to allow on the first pass.

    Append-only, no lock. Run one copy at a time. Readers de-duplicate.
    """
    if not CACHE.exists():
        return set()
    ids = set()
    with open(CACHE) as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if not r.get("error"):
                ids.add(str(r["facility_id"]))
    return ids


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--validate", type=int, default=250,
                    help="also measure this many facilities that already have a "
                         "known height, to quantify agreement")
    args = ap.parse_args()

    fp = gpd.read_file(FOOTPRINTS)
    attrs = pd.read_csv(ATTRS, low_memory=False)[["facility_id", "height_m"]]
    g = fp.merge(attrs, on="facility_id", how="left")
    g["pt"] = g.geometry.representative_point()

    proj = boundaries()
    pts = gpd.GeoDataFrame(g[["facility_id", "height_m"]], geometry=g["pt"],
                           crs="EPSG:4326")
    j = (gpd.sjoin(pts, proj, how="inner", predicate="within")
           .drop_duplicates("facility_id"))

    missing = j[j["height_m"].isna()]
    known = j[j["height_m"].notna()].sample(
        min(args.validate, int(j["height_m"].notna().sum())), random_state=20260811)
    todo = pd.concat([missing, known])
    have = done_ids()
    todo = todo[~todo["facility_id"].astype(str).isin(have)]
    if args.limit:
        todo = todo.head(args.limit)

    print(f"lidar-covered facilities {len(j)} | missing height {len(missing)} | "
          f"validation sample {len(known)}")
    print(f"cached {len(have)} | to measure {len(todo)}", flush=True)
    if not len(todo):
        return

    geom = dict(zip(g["facility_id"], g["geometry"]))
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    ok = err = 0
    t0 = time.time()
    with open(CACHE, "a") as out:
        for i, r in enumerate(todo.itertuples(), 1):
            fid = str(r.facility_id)
            rec = {"facility_id": fid, "project": r.project,
                   "known_height_m": None if pd.isna(r.height_m) else float(r.height_m)}
            try:
                rec.update(height_for(r.url, geom[r.facility_id]))
            except Exception as e:  # noqa: BLE001
                rec["error"] = f"{type(e).__name__}: {e}"[:200]
            ok, err = (ok + 1, err) if not rec.get("error") else (ok, err + 1)
            out.write(json.dumps(rec) + "\n")
            time.sleep(PACE_S)
            if i % 25 == 0:
                out.flush()
                rate = (time.time() - t0) / i
                print(f"  {i}/{len(todo)}  ok={ok} err={err}  "
                      f"{rate:.1f}s/site  eta {rate*(len(todo)-i)/60:.0f}min",
                      flush=True)
    print(f"done. measured {ok}, failed {err}")


if __name__ == "__main__":
    main()
