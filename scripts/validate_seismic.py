"""Validate sampled seismic values against the official USGS service, and
quantify the soil-class sensitivity.

Two things reviewers asked for that a sanity check cannot supply.

**1. Quantitative validation.** Our seismic column is sampled from the USGS NSHM
2023 *contour polygon* product at site class BC. The USGS ASCE 7-22 web service
returns ``pgam``, the site-modified MCEg peak ground acceleration, computed from
the same underlying model but delivered independently of the shapefiles and with
its own spatial interpolation. Agreement between the two is therefore a real
external check on the sampling, not a restatement of it.

Both are uniform-hazard 2%-in-50-year quantities. ``pgam`` is that mapped PGA
multiplied by the site coefficient F_PGA, and it does **not** depend on risk
category (verified directly: the service returns the same value for categories
I, III and IV). An earlier version of this script claimed ``pgam`` was
risk-targeted and used that to excuse the discrepancy. That was wrong, so the
disagreement is reported as a disagreement.

Because the service accepts ``siteClass=BC`` directly, the comparison is made at
the same site class our column uses, and the residual difference reflects
spatial interpolation and model delivery rather than a definitional gap.

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
SITE_CLASSES = ["BC", "B", "C", "D", "E"]


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
    ref = s["usgs_pgam_BC"]         # same site class as our column
    ok = ours.notna() & ref.notna()
    d = (ours[ok] - ref[ok])
    rel = 100 * d / ref[ok]

    stats = {
        "n_sampled": int(len(s)), "n_compared": int(ok.sum()), "seed": SEED,
        "our_column": "haz_seismic_pga_g_2475yr (uniform-hazard 2% in 50 yr, site class BC)",
        "reference": "USGS ASCE 7-22 pgam at siteClass=BC (uniform-hazard "
                     "2% in 50 yr mapped PGA x F_PGA; NOT risk-targeted)",
        "pearson_r": float(np.corrcoef(ours[ok], ref[ok])[0, 1]),
        "spearman_r": float(pd.Series(ours[ok]).corr(pd.Series(ref[ok]), method="spearman")),
        "median_bias_g": float(d.median()),
        "median_relative_bias_pct": float(rel.median()),
        "rmse_g": float(np.sqrt(np.mean(d ** 2))),
        "iqr_relative_bias_pct": [float(rel.quantile(0.25)), float(rel.quantile(0.75))],
        "range_relative_bias_pct": [float(rel.min()), float(rel.max())],
        "within_10pct": int((rel.abs() <= 10).sum()),
        "within_25pct": int((rel.abs() <= 25).sum()),
        "bias_vs_level_spearman": float(
            pd.Series(rel.to_numpy()).corr(pd.Series(ref[ok].to_numpy()),
                                           method="spearman")),
        "interpretation": "Both quantities are uniform-hazard 2% in 50 yr at the "
                          "same site class, so they should agree closely. They do "
                          "not. The bias is not a constant offset: it varies with "
                          "hazard level and spans a wide range, so a single median "
                          "would misrepresent it. The likely cause is that our "
                          "column is sampled from a cartographic CONTOUR product "
                          "(0.01 g bands) rather than the underlying gridded "
                          "model. Sampling the NSHM grid or hazard-curve service "
                          "directly is the recommended fix.",
    }
    # Bias by hazard level, since a single median hides the structure.
    q = pd.qcut(ref[ok], 5, duplicates="drop")
    stats["bias_by_quintile_pct"] = {
        str(k): round(float(v), 1) for k, v in rel.groupby(q, observed=True).median().items()}

    print("\n=== validation against USGS ===")
    print(f"  compared        : {stats['n_compared']}")
    print(f"  Pearson r       : {stats['pearson_r']:.4f}")
    print(f"  Spearman rho    : {stats['spearman_r']:.4f}")
    print(f"  median bias     : {stats['median_bias_g']:+.4f} g "
          f"({stats['median_relative_bias_pct']:+.1f}%)")
    print(f"  RMSE            : {stats['rmse_g']:.4f} g")
    print(f"  relative bias IQR: [{stats['iqr_relative_bias_pct'][0]:+.1f}%, "
          f"{stats['iqr_relative_bias_pct'][1]:+.1f}%]  range "
          f"[{stats['range_relative_bias_pct'][0]:+.1f}%, "
          f"{stats['range_relative_bias_pct'][1]:+.1f}%]")
    print(f"  within +/-10%   : {stats['within_10pct']}/{stats['n_compared']}"
          f"   within +/-25%: {stats['within_25pct']}/{stats['n_compared']}")
    print(f"  bias vs level (Spearman): {stats['bias_vs_level_spearman']:+.3f}"
          "   (non-zero means the bias is NOT a constant offset)")
    print("  bias by quintile of reference:", stats["bias_by_quintile_pct"])

    # --- soil sensitivity ------------------------------------------------------
    soil = {}
    base = s["usgs_pgam_B"]  # true rock reference
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
