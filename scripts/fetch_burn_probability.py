"""Annual wildfire burn probability per facility, on a 2.4 km buffer.

Why this exists. The exposure results use USFS Wildfire Hazard Potential, an
ordinal 1-to-5 index with no return period attached. Flood is defined at a
1%-annual-chance event and earthquake at 2% in 50 years, so wildfire cannot be
compared with either. Burn probability is an annual probability, so it converts
directly: return period = 1 / BP.

Source. USFS Wildfire Risk to Communities, 2024 version, BP_CONUS at 30 m,
served as an ArcGIS ImageServer. Sampling through the service avoids a 32.3 GB
download for values at 2,696 points.

**Integer scaling.** The service stores BP as U16 integers. Its reported maximum
is 1352 and the published BP range for CONUS is 0 to 0.14, so the scale is
10,000 and 1352 corresponds to 0.1352. No other power of ten is consistent with
both figures.

**Buffer, not point.** The wildfire exposure criterion is the maximum hazard
within 2.4 km, because most facilities sit on non-burnable land where the pixel
underneath carries no information. This mirrors that geometry using the service's
polygon statistics endpoint, so the two are directly comparable.

    ./.venv/bin/python scripts/fetch_burn_probability.py --limit 20
    ./.venv/bin/python scripts/fetch_burn_probability.py
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd
import pyproj
import requests
from shapely.geometry import Point
from shapely.ops import transform as shp_transform

REPO = Path(__file__).resolve().parents[1]
DC_CSV = REPO / "data" / "processed" / "datacenters_final.csv"
CACHE = REPO / "data" / "raw" / "burn_probability" / "burn_probability.jsonl"
URL = ("https://imagery.geoplatform.gov/iipp/rest/services/Fire_Aviation/"
       "USFS_EDW_RMRS_WRC_BurnProbability/ImageServer/computeStatisticsHistograms")

BP_SCALE = 10_000.0     # integer pixel value / BP_SCALE = annual probability
BUFFER_M = 2_400        # matches the wildfire exposure criterion
RETRIES = 3
PACE_S = 0.35           # be polite to a public service

SESSION = requests.Session()
SESSION.headers["User-Agent"] = (
    "datacenter-dataset/0.1 (academic research; GMU GeoAI)")

# Buffer in Albers Equal Area so 2,400 m means 2,400 m, then hand the service
# Web Mercator, which is what it serves in.
_TO_ALBERS = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True).transform
_TO_MERC = pyproj.Transformer.from_crs("EPSG:5070", "EPSG:3857", always_xy=True).transform


def buffer_rings(lon: float, lat: float):
    poly = shp_transform(_TO_MERC,
                         shp_transform(_TO_ALBERS, Point(lon, lat)).buffer(BUFFER_M))
    return [[list(c) for c in poly.exterior.coords]]


def sample(fid: str, lon: float, lat: float) -> dict:
    geom = {"rings": buffer_rings(lon, lat),
            "spatialReference": {"wkid": 102100}}
    body = {"geometry": json.dumps(geom),
            "geometryType": "esriGeometryPolygon", "f": "json"}
    last = None
    for attempt in range(RETRIES):
        try:
            j = SESSION.post(URL, data=body, timeout=120).json()
            stats = (j.get("statistics") or [{}])[0]
            if "max" not in stats:
                raise ValueError(str(j.get("error") or j)[:150])
            mx, mean = float(stats["max"]), float(stats.get("mean", "nan"))
            return {
                "facility_id": fid,
                "bp_max_2400m": mx / BP_SCALE,
                "bp_mean_2400m": mean / BP_SCALE,
                # A zero maximum means no burnable probability in range, which is
                # a measured result, not a missing one. Return period is then
                # undefined rather than infinite, so it is left null.
                "bp_return_period_yr": (BP_SCALE / mx) if mx > 0 else None,
                "error": None,
            }
        except Exception as e:  # noqa: BLE001 - retried, then recorded
            last = e
            time.sleep(1.5 * (attempt + 1))
    return {"facility_id": fid, "error": f"{type(last).__name__}: {last}"[:200]}


def done_ids() -> set[str]:
    """Append-only, unlocked. Run one copy at a time; readers de-duplicate."""
    if not CACHE.exists():
        return set()
    out = set()
    with open(CACHE) as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if not r.get("error"):
                out.add(str(r["facility_id"]))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    dc = pd.read_csv(DC_CSV, low_memory=False)
    have = done_ids()
    rows = [(str(r.facility_id), float(r.longitude), float(r.latitude))
            for r in dc.itertuples() if str(r.facility_id) not in have]
    if args.limit:
        rows = rows[: args.limit]
    print(f"facilities {len(dc)} | cached {len(have)} | to sample {len(rows)}",
          flush=True)
    if not rows:
        return

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    ok = err = 0
    t0 = time.time()
    with open(CACHE, "a") as out:
        for i, (fid, lon, lat) in enumerate(rows, 1):
            rec = sample(fid, lon, lat)
            ok, err = (ok + 1, err) if not rec.get("error") else (ok, err + 1)
            out.write(json.dumps(rec) + "\n")
            time.sleep(PACE_S)
            if i % 50 == 0:
                out.flush()
                rate = (time.time() - t0) / i
                print(f"  {i}/{len(rows)} ok={ok} err={err} {rate:.1f}s/site "
                      f"eta {rate*(len(rows)-i)/60:.0f}min", flush=True)
    print(f"done. sampled {ok}, failed {err}")


if __name__ == "__main__":
    main()
