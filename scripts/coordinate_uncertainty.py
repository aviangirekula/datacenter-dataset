"""How much does coordinate error change the hazard answer?

Hazard values inherit the positional accuracy of the coordinate they were
sampled at, and that accuracy varies a lot across this dataset: some coordinates
sit on a verified rooftop, others are an address geocode, a campus centroid, or
unresolved. Reporting one hazard value per facility hides that.

This runs a Monte Carlo. Each facility's coordinate is perturbed many times with
a tier-appropriate error, the hazard is re-sampled at every draw, and the
resulting spread is reported. The useful output is not a new hazard value but a
**stability measure**: how often the answer changes when the coordinate moves
within its own uncertainty.

Error scales by tier (metres, 1 sigma, isotropic Gaussian):

===================================  ======  ==================================
tier                                 sigma   rationale
===================================  ======  ==================================
coordinate inside a building          10     the building itself constrains it
verified / nearest within 200 m       30     parcel scale
address geocode                      100     street-segment interpolation
campus centroid                      250     site scale, not building scale
unresolved / unknown                 500     lower bound on the real error
===================================  ======  ==================================

Expect this to be near-inert for seismic and lightning, whose correlation
lengths are tens of kilometres, and material for wildfire at 270 m. A null
result for the first two is itself worth reporting: it means those columns are
robust to the dataset's positional error.

    ./.venv/bin/python scripts/coordinate_uncertainty.py [--draws 50]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from dcdata.hazards.sample import sample_raster_at_points

REPO = Path(__file__).resolve().parents[1]
DC_CSV = REPO / "data" / "processed" / "datacenters_final.csv"
ATTR = REPO / "data" / "processed" / "building_attributes.csv"
HAZ_DIR = REPO / "data" / "hazards"
WHP_TIF = HAZ_DIR / "wildfire" / "whp" / "Data" / "whp2023_GeoTIF" / "whp2023_cls_conus.tif"
LIGHTNING_TIF = HAZ_DIR / "data" / "hotspots" / "lightning_annual_rate_4326.tif"
OUT = REPO / "data" / "processed" / "coordinate_uncertainty.csv"
OUT_JSON = REPO / "data" / "processed" / "coordinate_uncertainty.json"

SIGMA_M = {"building": 10.0, "verified": 30.0, "geocoded_address": 100.0,
           "campus_centroid": 250.0, "unknown": 500.0}
SEED = 20260731  # fixed so the run is reproducible


def assign_sigma(dc: pd.DataFrame, attr: pd.DataFrame) -> np.ndarray:
    """Pick a positional sigma per facility from the strongest available signal."""
    m = dc.merge(attr[["facility_id", "building_match", "building_dist_m"]],
                 on="facility_id", how="left")
    sig = np.full(len(m), SIGMA_M["unknown"])
    prec = m.get("coordinate_precision", pd.Series([None] * len(m)))
    sig = np.where(prec == "geocoded_address", SIGMA_M["geocoded_address"], sig)
    sig = np.where(prec == "campus_centroid", SIGMA_M["campus_centroid"], sig)
    sig = np.where(prec == "building", SIGMA_M["verified"], sig)
    # Falling inside a building polygon tightens a coordinate only if the source
    # already claimed building precision. A street-segment geocode that happens
    # to land inside a footprint is still a street-segment geocode, and treating
    # 797 such records as 10 m was the largest single distortion in an earlier
    # version of this analysis.
    inside = (m["building_match"] == "contains").to_numpy()
    sig = np.where(inside & (prec == "building").to_numpy(),
                   SIGMA_M["building"], sig)
    # The 30 m tier is meant to be "within a parcel", so require it.
    dist = pd.to_numeric(m.get("building_dist_m"), errors="coerce").to_numpy()
    far = np.isfinite(dist) & (dist > 200)
    sig = np.where(far & (sig < SIGMA_M["geocoded_address"]),
                   SIGMA_M["geocoded_address"], sig)
    return sig


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=500)
    args = ap.parse_args()

    dc = pd.read_csv(DC_CSV, low_memory=False)
    attr = pd.read_csv(ATTR, low_memory=False)
    lon = dc["longitude"].astype(float).to_numpy()
    lat = dc["latitude"].astype(float).to_numpy()
    n = len(dc)
    sigma = assign_sigma(dc, attr)
    print(f"facilities: {n} | draws: {args.draws}")
    print("sigma assignment:",
          {f"{v:.0f} m": int((sigma == v).sum()) for v in sorted(set(sigma))})

    rng = np.random.default_rng(SEED)
    # Metres -> degrees. Longitude degrees shrink with latitude.
    dlat = sigma / 111_320.0
    dlon = sigma / (111_320.0 * np.cos(np.radians(lat)))

    base_whp = sample_raster_at_points(WHP_TIF, lon, lat)
    base_lit = sample_raster_at_points(LIGHTNING_TIF, lon, lat)

    whp_changes = np.zeros(n)
    lit_vals = np.zeros((args.draws, n))
    for d in range(args.draws):
        jlon = lon + rng.normal(0, 1, n) * dlon
        jlat = lat + rng.normal(0, 1, n) * dlat
        w = sample_raster_at_points(WHP_TIF, jlon, jlat)
        lit_vals[d] = sample_raster_at_points(LIGHTNING_TIF, jlon, jlat)
        whp_changes += (w != base_whp) & np.isfinite(w) & np.isfinite(base_whp)
        if (d + 1) % 10 == 0:
            print(f"  draw {d + 1}/{args.draws}")

    whp_p_change = whp_changes / args.draws
    lit_cv = np.nanstd(lit_vals, axis=0) / np.where(
        np.abs(base_lit) > 0, np.abs(base_lit), np.nan)

    out = dc[["facility_id", "name", "state", "coordinate_precision"]].copy()
    out["positional_sigma_m"] = sigma
    out["whp_class_change_prob"] = whp_p_change
    out["lightning_rel_sd"] = lit_cv

    stats = {
        "draws": args.draws, "seed": SEED,
        "sigma_m_by_tier": SIGMA_M,
        "wildfire": {
            "mean_class_change_prob": float(np.nanmean(whp_p_change)),
            "facilities_over_25pct_change": int((whp_p_change > 0.25).sum()),
            "facilities_stable": int((whp_p_change < 0.05).sum()),
        },
        "lightning": {
            "median_relative_sd": float(np.nanmedian(lit_cv)),
            "facilities_that_moved_at_all": int(np.nansum(lit_cv > 0)),
            "max_relative_sd": float(np.nanmax(lit_cv)),
            "note": "The median is 0 by construction: on a 0.5 degree grid only "
                    "points within sigma of a cell edge can move at all, so the "
                    "informative statistics are how many moved and by how much.",
        },
        "by_tier": {},
    }
    for s in sorted(set(sigma)):
        sel = sigma == s
        stats["by_tier"][f"sigma_{int(s)}m"] = {
            "n": int(sel.sum()),
            "mean_whp_change_prob": float(np.nanmean(whp_p_change[sel])),
        }

    print("\n=== wildfire class stability ===")
    print(f"  mean probability the class changes: {stats['wildfire']['mean_class_change_prob']:.3f}")
    print(f"  facilities changing >25% of draws : {stats['wildfire']['facilities_over_25pct_change']}")
    print(f"  facilities stable (<5% of draws)  : {stats['wildfire']['facilities_stable']}")
    print("\n  by positional sigma:")
    for k, v in stats["by_tier"].items():
        print(f"    {k:>12s}: n={v['n']:5d}  mean change prob {v['mean_whp_change_prob']:.3f}")
    print("\n=== lightning ===")
    print(f"  facilities whose value moved at all: "
          f"{stats['lightning']['facilities_that_moved_at_all']} of {n}")
    print(f"  max relative SD: {stats['lightning']['max_relative_sd']:.4f}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    OUT_JSON.write_text(json.dumps(stats, indent=2) + "\n")
    print(f"\nWrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
