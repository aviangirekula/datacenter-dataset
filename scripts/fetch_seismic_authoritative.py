"""Replace contour-sampled seismic values with authoritative per-point values.

Validation against the USGS ASCE 7-22 service showed the contour-sampled column
disagrees badly in magnitude: only 22 of 150 sampled facilities agreed within
10%, with relative error spanning -54% to +130% and varying systematically with
hazard level. The spatial pattern was right (Spearman 0.83) but the numbers were
not, because a cartographic contour product quantises to 0.01 g bands and its
polygons are generalised for display.

This queries the USGS ASCE 7-22 web service once per facility at
``siteClass=BC``, the same reference condition the dataset documents, and stores
the value the USGS itself reports for that exact coordinate. No interpolation of
ours is involved.

**What this fixes and what it does not.** The service returns MCE_G peak ground
acceleration, which is the 2% in 50 year (about 2,475 year) level. That column
becomes authoritative. The 475 and 975 year columns have no equivalent public
point service and remain contour-derived, so they keep the documented
discretisation caveat and should be treated as approximate.

Also captured, because they cost nothing extra and the storey control needs
them: ``ss`` and ``s1``, the short-period and 1 second spectral accelerations.
Spectral acceleration near 1 second, not PGA, is the demand parameter that
actually distinguishes a tall building from a low one.

    ./.venv/bin/python scripts/fetch_seismic_authoritative.py
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
CACHE = REPO / "data" / "raw" / "seismic_points_multilevel.jsonl"
URL = "https://earthquake.usgs.gov/ws/designmaps/asce7-22.json"
# ASCE 41-17 reports several hazard levels in one call, which ASCE 7 does not.
# BSE-2E is 5% in 50 years (about 975 yr) and BSE-1E is 20% in 50 years (about
# 225 yr). Only spectral accelerations are returned, not PGA, but these are the
# only authoritative multi-level values available from a public point service.
URL41 = "https://earthquake.usgs.gov/ws/designmaps/asce41-17.json"
UA = {"User-Agent": "datacenter-dataset/0.1 (academic research; GMU GeoAI)"}
SITE_CLASS = "BC"
WORKERS = 5
RETRIES = 3


def fetch(fid: str, lat: float, lon: float) -> dict:
    q = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon, "riskCategory": "III",
        "siteClass": SITE_CLASS, "title": "dc"})
    last = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(f"{URL}?{q}", headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.loads(r.read().decode("utf8"))
            data = d.get("response", {}).get("data", {}) or {}
            meta = d.get("response", {}).get("metadata", {}) or {}
            rec = {"facility_id": fid, "lat": lat, "lon": lon,
                   "site_class": SITE_CLASS, "error": None,
                   "pgam": data.get("pgam"), "ss": data.get("ss"),
                   "s1": data.get("s1"), "sds": data.get("sds"),
                   "sd1": data.get("sd1"), "sdc": data.get("sdc"),
                   "vs30": meta.get("vs30"),
                   "model_version": meta.get("modelVersion")}
            rec.update(fetch_asce41(lat, lon))
            return rec
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.0 * (attempt + 1))
    return {"facility_id": fid, "lat": lat, "lon": lon, "site_class": SITE_CLASS,
            "error": f"{type(last).__name__}: {last}"}


def fetch_asce41(lat: float, lon: float) -> dict:
    """Spectral accelerations at the ASCE 41 hazard levels.

    Returns empty values rather than failing the whole record, since the ASCE 7
    value is the primary quantity and these are supplementary.
    """
    q = urllib.parse.urlencode({"latitude": lat, "longitude": lon,
                                "siteClass": SITE_CLASS, "title": "dc"})
    out: dict = {}
    try:
        req = urllib.request.Request(f"{URL41}?{q}", headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read().decode("utf8"))
        for entry in d.get("response", {}).get("data", []) or []:
            lvl = entry.get("hazardLevel")
            if lvl in ("BSE-2E", "BSE-1E", "BSE-2N"):
                key = lvl.lower().replace("-", "_")
                out[f"{key}_ss"] = entry.get("ss")
                out[f"{key}_s1"] = entry.get("s1")
    except Exception:  # noqa: BLE001 - supplementary, never fatal
        pass
    return out


def done_ids() -> set[str]:
    """Facility ids already cached without error.

    NOTE: this file is append-only and there is no lock. Running two copies of
    this script at once makes both compute the same todo list and append the
    same records, which is how an earlier run produced 2,992 duplicate rows.
    Run one at a time. Readers de-duplicate defensively.
    """
    if not CACHE.exists():
        return set()
    ids = set()
    with open(CACHE) as fh:
        for line in fh:
            try:
                r = json.loads(line)
                if not r.get("error"):
                    ids.add(r["facility_id"])
            except Exception:  # noqa: BLE001
                continue
    return ids


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    dc = pd.read_csv(DC_CSV, low_memory=False)
    rows = [(str(r.facility_id), float(r.latitude), float(r.longitude))
            for r in dc.itertuples()]
    if args.limit:
        rows = rows[: args.limit]
    have = done_ids()
    todo = [r for r in rows if r[0] not in have]
    print(f"facilities {len(rows)} | cached {len(have)} | to fetch {len(todo)}")
    if not todo:
        return

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    n_err = 0
    with open(CACHE, "a") as out, ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for i, rec in enumerate(ex.map(lambda r: fetch(*r), todo), 1):
            if rec.get("error"):
                n_err += 1
            out.write(json.dumps(rec) + "\n")
            if i % 200 == 0:
                out.flush()
                print(f"  {i}/{len(todo)}  errors={n_err}")
    print(f"done, {n_err} errors")


if __name__ == "__main__":
    main()
