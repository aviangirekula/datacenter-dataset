"""Sample the USGS National Seismic Hazard Model for per-facility hazard curves.

Why this exists. ``fetch_seismic_authoritative.py`` made the 2,475 year PGA
column authoritative by querying the ASCE 7-22 design maps service, but that
service reports one hazard level. The 475 and 975 year columns stayed
contour-derived, and validation showed the contour product's magnitudes are
unreliable (only 22 of 150 sampled facilities within 10%, median relative bias
+32%). This script replaces both with values read off the NSHM's own hazard
curve at each facility.

How. The NSHM static service returns a PGA hazard curve, ground motion against
annual frequency of exceedance, at a given point and NEHRP site class. A return
period of N years is an annual exceedance frequency of 1/N, so each level is a
single interpolation along that curve. Interpolation is done in log-log space,
which is how hazard curves are conventionally read, because both axes span
orders of magnitude and linear interpolation across a decade is badly wrong.

Site class BC is passed by name, which is the reference site condition this
dataset documents and the same condition the ASCE 7-22 queries used.

**Static, not dynamic.** The service has two endpoints. ``dynamic`` recomputes
hazard on request and measured 1.4 to 15 seconds per site at 650 to 790 kB;
``static`` reads precomputed curves from a NetCDF file and measured 0.25 to 0.43
seconds at 28 kB, for the same curve. Dynamic also takes Vs30 in m/s while
static takes the NEHRP class directly, which is the quantity actually meant
here. Dynamic was tried first and is not worth the 30x cost.

**Rate limit.** The service allows 300 requests per 5 minute window and says so
in its own 429 body. That is one request per second, which is the binding
constraint rather than response time, so this runs single-threaded on a paced
clock. Expect roughly 50 minutes for a full cold run.

**A vintage caveat worth stating plainly.** This queries the 2023 Conterminous
US model. The ASCE 7-22 service is a design-code product built on an earlier
model revision, so its 2,475 year value and the NSHM's are not required to
agree. That is exactly why this script also records the NSHM 2,475 year level:
it makes the difference measurable instead of hidden. ``build_hazard_exposure``
compares the two and writes the spread to ``hazard_exposure_coverage.json``
under ``seismic_nshm.nshm_vs_asce7_at_2475yr``. All three NSHM levels come from one
model and one curve, so they are internally consistent with each other.

    ./.venv/bin/python scripts/fetch_seismic_nshm.py
    ./.venv/bin/python scripts/fetch_seismic_nshm.py --limit 20
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request

from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
DC_CSV = REPO / "data" / "processed" / "datacenters_final.csv"
CACHE = REPO / "data" / "raw" / "seismic_nshm_curves.jsonl"

# The unversioned path 302-redirects to the current revision and the redirect
# downgrades to http, which drops the query string on some clients. Pinning the
# revision keeps the request deterministic and reproducible, and records exactly
# which model produced the numbers.
MODEL = "conus-2023.R2"
URL = f"https://earthquake.usgs.gov/ws/nshmp/{MODEL}/static/hazard"
# Path form, not query form. The query form returns the usage document.
UA = {"User-Agent": "datacenter-dataset/0.1 (academic research; GMU GeoAI)"}
SITE_CLASS = "BC"               # NEHRP B/C boundary, the reference condition
RETURN_PERIODS = (475, 975, 2475)
RETRIES = 5
TIMEOUT = 60
# The service publishes 300 requests per 5 minutes. One request per second sits
# exactly on that, so pace slightly under it and leave headroom for retries.
MIN_INTERVAL_S = 1.1
# A 429 means the whole 5 minute window is spent, so short backoff is useless.
BACKOFF_429_S = 305


def levels_from_curve(xs: list[float], ys: list[float]) -> dict:
    """Ground motion at each return period, by log-log interpolation.

    ``xs`` is ground motion in g, ascending. ``ys`` is annual frequency of
    exceedance, descending. numpy.interp needs an ascending x, so both are
    reversed to interpolate exceedance -> ground motion.

    Returns None for a level that falls outside the curve rather than
    extrapolating. A flat zero-seismicity site genuinely has no 2,475 year
    ground motion within the tabulated range, and inventing one by extrapolating
    off the end of a log-log curve would be a fabricated number.
    """
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    keep = (y > 0) & np.isfinite(x) & np.isfinite(y)
    x, y = x[keep], y[keep]
    out: dict = {}
    for rp in RETURN_PERIODS:
        target = 1.0 / rp
        if len(x) < 2 or target > y.max() or target < y.min():
            out[f"pga_g_{rp}yr"] = None
            continue
        # y descends with x, so reverse both to get an ascending interpolant.
        out[f"pga_g_{rp}yr"] = float(
            np.exp(np.interp(np.log(target), np.log(y)[::-1], np.log(x)[::-1])))
    return out


def parse(payload: dict) -> dict:
    """Pull the PGA curve out of a static-service response.

    Defensive about shape on purpose. When the service throttles or errors it
    still returns JSON, but ``response`` is a plain string holding the message
    rather than the usual list. Reading that as a list is what produced a batch
    of bare AttributeErrors on the first run, which said nothing about the
    actual cause. Now the message is surfaced.
    """
    resp = payload.get("response")
    if isinstance(resp, str):
        raise ValueError(f"service message: {resp[:160]}")
    if not isinstance(resp, list):
        raise ValueError(f"unexpected response type {type(resp).__name__}")
    pga = None
    for entry in resp:
        imt = (entry.get("metadata") or {}).get("imt")
        # imt is normally {"value": "PGA"}, but tolerate a bare string.
        value = imt.get("value") if isinstance(imt, dict) else imt
        if value == "PGA":
            pga = entry
            break
    if pga is None:
        raise ValueError("no PGA curve in response")
    vals = pga.get("data") or {}
    xs, ys = vals.get("xs"), vals.get("ys")
    if not xs or not ys or len(xs) != len(ys):
        raise ValueError("malformed PGA curve values")
    rec = {"xs": xs, "ys": ys}
    rec.update(levels_from_curve(xs, ys))
    return rec


def fetch(fid: str, lat: float, lon: float) -> dict:
    """One site. Blocks on 429 rather than burning retries against a closed
    window, since the limit is per 5 minutes and nothing shorter will clear it.
    """
    url = f"{URL}/{lon}/{lat}/{SITE_CLASS}"
    base = {"facility_id": fid, "lat": lat, "lon": lon,
            "site_class": SITE_CLASS, "model": MODEL}
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                payload = json.loads(r.read().decode("utf8"))
            return {**base, "error": None, **parse(payload)}
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                print(f"    429 rate limited, sleeping {BACKOFF_429_S}s",
                      flush=True)
                time.sleep(BACKOFF_429_S)
            else:
                time.sleep(2.0 * (attempt + 1))
        except Exception as e:  # noqa: BLE001 - retried, then recorded
            last = e
            time.sleep(2.0 * (attempt + 1))
    return {**base, "error": f"{type(last).__name__}: {last}"}


def done_ids() -> set[str]:
    """Facility ids already cached without error.

    NOTE: append-only, no lock. Two copies of this script running at once will
    build the same todo list and append the same records, which is how an
    earlier fetcher produced 2,992 duplicate rows. Run one at a time. Readers
    de-duplicate defensively.
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


def load_levels() -> pd.DataFrame:
    """Cached NSHM levels, de-duplicated, keeping the last good row per id."""
    if not CACHE.exists():
        return pd.DataFrame()
    rows = []
    with open(CACHE) as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if r.get("error"):
                continue
            rows.append({"facility_id": str(r["facility_id"]),
                         **{f"pga_g_{rp}yr": r.get(f"pga_g_{rp}yr")
                            for rp in RETURN_PERIODS}})
    if not rows:
        return pd.DataFrame()
    return (pd.DataFrame(rows)
            .drop_duplicates(subset="facility_id", keep="last")
            .reset_index(drop=True))


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
    print(f"model {MODEL} | site class {SITE_CLASS} | levels {RETURN_PERIODS}")
    print(f"paced at {MIN_INTERVAL_S}s/request, about "
          f"{len(todo) * MIN_INTERVAL_S / 60:.0f} min", flush=True)
    if not todo:
        return

    # Single-threaded on a paced clock. Concurrency buys nothing when the server
    # allows one request per second, and it is what tripped the limiter before.
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    n_err = 0
    next_at = 0.0
    with open(CACHE, "a") as out:
        for i, row in enumerate(todo, 1):
            wait = next_at - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            next_at = time.monotonic() + MIN_INTERVAL_S
            rec = fetch(*row)
            if rec.get("error"):
                n_err += 1
            out.write(json.dumps(rec) + "\n")
            if i % 100 == 0:
                out.flush()
                print(f"  {i}/{len(todo)}  errors={n_err}", flush=True)
    print(f"done, {n_err} errors")


if __name__ == "__main__":
    main()
