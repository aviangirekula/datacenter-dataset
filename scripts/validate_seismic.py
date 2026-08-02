"""Validate sampled seismic values against the official USGS service, and
quantify the soil-class sensitivity.

Two things reviewers asked for that a sanity check cannot supply.

**1. Quantitative validation.** Our seismic column is sampled from the USGS NSHM
2023 *contour polygon* product at site class BC. The USGS ASCE 7-22 web service
returns ``pgam``, the site-modified MCEg peak ground acceleration, computed from
the same underlying model but delivered independently of the shapefiles and with
its own spatial interpolation. Agreement between the two is therefore a real
external check on the sampling, not a restatement of it.

The two are related but not identical quantities:

- ours is a **uniform-hazard** 2%-in-50-year PGA at reference rock (site class BC),
- ``pgam`` is a **risk-targeted, site-modified** MCEg value.

So the expectation is a strong monotonic relationship with a systematic offset,
not equality. The offset is reported rather than explained away.

**2. Soil sensitivity.** Our values assume reference rock. Many of the largest
data-center clusters sit on soft ground, where motion amplifies. Querying the
same points at several site classes measures that directly and replaces the
qualitative caveat in the docs with a number.

    ./.venv/bin/python scripts/validate_seismic.py [--n 150]
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
HAZ = REPO / "data" / "processed" / "hazard_exposure.csv"
OUT_JSON = REPO / "data" / "processed" / "seismic_validation.json"
OUT_CSV = REPO / "data" / "processed" / "seismic_validation.csv"

URL = "https://earthquake.usgs.gov/ws/designmaps/asce7-22.json"
UA = {"User-Agent": "datacenter-dataset/0.1 (academic research; GMU GeoAI)"}
SEED = 20260731
SITE_CLASSES = ["B", "C", "D", "E"]


def query(lat: float, lon: float, site_class: str) -> float | None:
    q = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon, "riskCategory": "III",
        "siteClass": site_class, "title": "dc"})
    for attempt in range(3):
        try:
            req = urllib.request.Request(f"{URL}?{q}", headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.loads(r.read().decode("utf8"))
            return d.get("response", {}).get("data", {}).get("pgam")
        except Exception:  # noqa: BLE001
            time.sleep(1.0 * (attempt + 1))
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150, help="random facilities to check")
    args = ap.parse_args()

    haz = pd.read_csv(HAZ, low_memory=False)
    rng = np.random.default_rng(SEED)
    idx = rng.choice(len(haz), size=min(args.n, len(haz)), replace=False)
    s = haz.iloc[idx][["facility_id", "name", "state", "latitude", "longitude",
                       "haz_seismic_pga_g_2475yr"]].copy().reset_index(drop=True)
    print(f"validating {len(s)} random facilities against USGS ASCE 7-22 ...")

    for sc in SITE_CLASSES:
        with ThreadPoolExecutor(max_workers=5) as ex:
            vals = list(ex.map(lambda r: query(r[0], r[1], sc),
                               zip(s["latitude"], s["longitude"])))
        s[f"usgs_pgam_{sc}"] = pd.to_numeric(vals, errors="coerce")
        got = s[f"usgs_pgam_{sc}"].notna().sum()
        print(f"  site class {sc}: {got}/{len(s)} returned")

    ours = s["haz_seismic_pga_g_2475yr"]
    ref = s["usgs_pgam_C"]          # closest single class to our BC reference
    ok = ours.notna() & ref.notna()
    d = (ours[ok] - ref[ok])
    rel = 100 * d / ref[ok]

    stats = {
        "n_sampled": int(len(s)), "n_compared": int(ok.sum()), "seed": SEED,
        "our_column": "haz_seismic_pga_g_2475yr (uniform-hazard 2% in 50 yr, site class BC)",
        "reference": "USGS ASCE 7-22 pgam (risk-targeted MCEg, site-modified)",
        "pearson_r": float(np.corrcoef(ours[ok], ref[ok])[0, 1]),
        "spearman_r": float(pd.Series(ours[ok]).corr(pd.Series(ref[ok]), method="spearman")),
        "median_bias_g": float(d.median()),
        "median_relative_bias_pct": float(rel.median()),
        "rmse_g": float(np.sqrt(np.mean(d ** 2))),
        "interpretation": "The two are related but distinct quantities "
                          "(uniform-hazard reference-rock versus risk-targeted "
                          "site-modified), so a strong rank correlation with a "
                          "systematic offset is the expected result. Rank "
                          "agreement is the meaningful validation.",
    }

    print("\n=== validation against USGS ===")
    print(f"  compared        : {stats['n_compared']}")
    print(f"  Pearson r       : {stats['pearson_r']:.4f}")
    print(f"  Spearman rho    : {stats['spearman_r']:.4f}")
    print(f"  median bias     : {stats['median_bias_g']:+.4f} g "
          f"({stats['median_relative_bias_pct']:+.1f}%)")
    print(f"  RMSE            : {stats['rmse_g']:.4f} g")

    # --- soil sensitivity ------------------------------------------------------
    soil = {}
    base = s["usgs_pgam_B"]
    for sc in SITE_CLASSES:
        col = s[f"usgs_pgam_{sc}"]
        m = base.notna() & col.notna()
        soil[sc] = {
            "median_pgam_g": float(col[m].median()),
            "median_ratio_to_B": float((col[m] / base[m]).median()),
        }
    stats["soil_sensitivity"] = soil
    print("\n=== soil-class sensitivity (median pgam, and ratio to class B rock) ===")
    for sc, v in soil.items():
        print(f"  class {sc}: {v['median_pgam_g']:.3f} g   x{v['median_ratio_to_B']:.2f}")
    worst = max(soil.values(), key=lambda v: v["median_ratio_to_B"])
    print(f"\n  Reference-rock values understate soft-soil motion by up to "
          f"{100 * (worst['median_ratio_to_B'] - 1):.0f}% at these sites.")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    s.to_csv(OUT_CSV, index=False)
    OUT_JSON.write_text(json.dumps(stats, indent=2) + "\n")
    print(f"\nWrote {OUT_JSON.relative_to(REPO)}")


if __name__ == "__main__":
    main()
