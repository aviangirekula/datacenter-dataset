"""Baseline water stress per facility, from WRI Aqueduct 4.0.

Data centers consume large volumes of water for evaporative cooling, so water
availability is a siting and operating constraint even though it is not a
natural hazard in the sense the other layers are. It is reported separately for
that reason and should not be folded into a hazard index.

Aqueduct 4.0 publishes indicators on hydrological basin polygons. Each facility
takes the value of the basin it falls in. ``bws_raw`` is the baseline
water-stress ratio (withdrawals over available supply) and ``bws_cat`` is
WRI's category, where higher means more stressed and -1 marks an arid basin with
low water use, which is a distinct condition rather than a low score.

    ./.venv/bin/python scripts/build_water_stress.py
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
DC_CSV = REPO / "data" / "processed" / "datacenters_final.csv"
OUT = REPO / "data" / "processed" / "water_stress.csv"
OUT_JSON = REPO / "data" / "processed" / "water_stress_coverage.json"

# WRI's own labels for bws_cat.
CAT = {-1: "arid_and_low_water_use", 0: "low", 1: "low_to_medium",
       2: "medium_to_high", 3: "high", 4: "extremely_high"}


def main() -> None:
    gdbs = glob.glob(str(REPO / "data" / "hazards" / "water" / "**" / "*.gdb"),
                     recursive=True)
    if not gdbs:
        raise SystemExit("Aqueduct GDB not found; run the download first")

    dc = pd.read_csv(DC_CSV, low_memory=False)
    pts = gpd.GeoDataFrame(
        dc[["facility_id", "name", "state"]].copy(),
        geometry=gpd.points_from_xy(dc["longitude"], dc["latitude"]),
        crs="EPSG:4326")

    print("reading Aqueduct baseline_annual ...")
    cols = ["bws_raw", "bws_score", "bws_cat", "bws_label", "geometry"]
    basins = gpd.read_file(gdbs[0], layer="baseline_annual")
    keep = [c for c in cols if c in basins.columns]
    basins = basins[keep].to_crs("EPSG:4326")
    print(f"  {len(basins):,} basins, columns {keep}")

    j = gpd.sjoin(pts, basins, how="left", predicate="within")
    # A point on a basin boundary can match twice; keep the more stressed.
    if "bws_score" in j.columns:
        j = j.sort_values("bws_score", ascending=False)
    j = j[~j.index.duplicated(keep="first")].sort_index()

    out = pd.DataFrame({"facility_id": j["facility_id"], "name": j["name"],
                        "state": j["state"]})
    for c in ("bws_raw", "bws_score", "bws_cat", "bws_label"):
        if c in j.columns:
            out[f"water_{c}"] = j[c].to_numpy()
    if "water_bws_cat" in out.columns:
        out["water_stress_class"] = pd.to_numeric(
            out["water_bws_cat"], errors="coerce").map(CAT)

    matched = int(out.filter(like="water_bws").notna().any(axis=1).sum())
    stats = {
        "n_facilities": int(len(out)), "matched_to_basin": matched,
        "source": "WRI Aqueduct 4.0 baseline annual (files.wri.org)",
        "indicator": "bws = baseline water stress, withdrawals / available supply",
        "note": "Water stress is a resource-availability constraint relevant to "
                "evaporative cooling, not a natural hazard. It is reported "
                "separately and should not be combined into a hazard index. "
                "Category -1 means arid with low water use, a distinct "
                "condition rather than a low score.",
    }
    print(f"\nmatched to a basin: {matched}/{len(out)}")
    if "water_stress_class" in out.columns:
        vc = out["water_stress_class"].value_counts(dropna=False)
        print(vc.to_string())
        stats["class_counts"] = {str(k): int(v) for k, v in vc.items()}
        high = out["water_stress_class"].isin(["high", "extremely_high"]).sum()
        stats["facilities_high_or_extreme"] = int(high)
        print(f"\nfacilities in high or extremely high water stress: {high}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    OUT_JSON.write_text(json.dumps(stats, indent=2) + "\n")
    print(f"Wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
