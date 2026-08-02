"""Per-facility severe-storm exposure from NOAA SPC event tracks.

Tornado, hail and damaging-wind hazards are published as historical event
records rather than hazard surfaces, so exposure is expressed as a **Poisson
event rate**: the number of recorded events whose track passes within a radius
of the facility, divided by the length of the record.

    rate (events/yr) = events within R km / record length in years

Two decisions carry the methodological weight, and both are stated rather than
buried:

**1. Reporting bias.** SPC records are *reports*, not a complete census. Report
density rises with population and with detection capability, and tornado and
hail counts increase sharply through the record as radar coverage improved.
Counting every report would therefore measure observer density as much as
hazard. Two mitigations are applied and reported side by side:

- a **significant-event** threshold, which is far less sensitive to reporting
  practice (EF2+ tornado, hail 2 inches or larger, wind 65 knots or more), and
- a **modern-era** window for the all-event rates.

Both the all-event and significant-event rates are written out. The
significant-event rate is the defensible one for comparison across regions.

**2. Radius.** A 40 km radius (about 25 miles) is a common convention in
tornado climatology and is wide enough that a single facility's rate is not
dominated by whether one track happened to clip it. The radius is a parameter,
and the sensitivity to it should be reported.

    ./.venv/bin/python scripts/build_storm_exposure.py
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
DC_CSV = REPO / "data" / "processed" / "datacenters_final.csv"
STORM_DIR = REPO / "data" / "hazards" / "storms"
OUT = REPO / "data" / "processed" / "storm_exposure.csv"
OUT_JSON = REPO / "data" / "processed" / "storm_exposure_coverage.json"

EQUAL_AREA = "EPSG:5070"
RADIUS_M = 40_000.0
# Reporting practice stabilised for hail/wind after the mid-1990s.
MODERN_FROM = 1996

DATASETS = {
    "tornado": {
        "dir": "1950-2024-torn-aspath",
        "first_year": 1950,
        # F/EF scale. EF2+ is the standard "significant tornado" threshold.
        "sig": lambda g: g["mag"] >= 2,
        "sig_label": "EF2 or greater",
    },
    "hail": {
        "dir": "1955-2024-hail-aspath",
        "first_year": 1955,
        # Diameter in inches. 2 inches is the SPC "significant hail" threshold.
        "sig": lambda g: g["mag"] >= 2.0,
        "sig_label": "2 inch diameter or greater",
    },
    "wind": {
        "dir": "1955-2024-wind-aspath",
        "first_year": 1955,
        # Knots. 65 kt (about 75 mph) is the SPC "significant wind" threshold.
        "sig": lambda g: g["mag"] >= 65,
        "sig_label": "65 knots or greater",
    },
}
LAST_YEAR = 2024


def _rate(counts: np.ndarray, years: int) -> np.ndarray:
    return counts / float(years)


def main() -> None:
    dc = pd.read_csv(DC_CSV, low_memory=False)
    pts = gpd.GeoDataFrame(
        {"facility_id": dc["facility_id"].astype(str)},
        geometry=gpd.points_from_xy(dc["longitude"], dc["latitude"]),
        crs="EPSG:4326").to_crs(EQUAL_AREA)
    pts["_i"] = np.arange(len(pts))
    buf = pts.copy()
    buf["geometry"] = buf.geometry.buffer(RADIUS_M)

    out = dc[["facility_id", "name", "state", "latitude", "longitude"]].copy()
    meta: dict[str, dict] = {}
    n = len(dc)

    for key, cfg in DATASETS.items():
        shp = STORM_DIR / cfg["dir"] / f"{cfg['dir']}.shp"
        if not shp.exists():
            print(f"  [skip] {key}: {shp.name} missing")
            continue
        print(f"\n{key}: reading {shp.name} ...")
        g = gpd.read_file(shp)
        g = g[g.geometry.notna() & ~g.geometry.is_empty]
        if g.crs is None:
            g = g.set_crs("EPSG:4326")
        g = g.to_crs(EQUAL_AREA)
        g["mag"] = pd.to_numeric(g["mag"], errors="coerce")
        g["yr"] = pd.to_numeric(g["yr"], errors="coerce")

        full_years = LAST_YEAR - cfg["first_year"] + 1
        modern_years = LAST_YEAR - MODERN_FROM + 1

        subsets = {
            # All events, modern era only, to limit the detection-era trend.
            f"{key}_all_rate_per_yr": (g[g["yr"] >= MODERN_FROM], modern_years),
            # Significant events over the full record. Least biased.
            f"{key}_sig_rate_per_yr": (g[cfg["sig"](g)], full_years),
        }

        for col, (sub, years) in subsets.items():
            if len(sub) == 0:
                out[col] = 0.0
                continue
            j = gpd.sjoin(buf[["_i", "geometry"]], sub[["geometry"]],
                          how="inner", predicate="intersects")
            counts = j.groupby("_i").size().reindex(range(n), fill_value=0).to_numpy()
            out[col] = _rate(counts, years)
            print(f"  {col}: median {np.median(out[col]):.3f}/yr  "
                  f"max {out[col].max():.3f}/yr  (n_events={len(sub):,}, {years} yr)")

        meta[key] = {
            "record": f"{cfg['first_year']}-{LAST_YEAR}",
            "modern_window": f"{MODERN_FROM}-{LAST_YEAR}",
            "significant_threshold": cfg["sig_label"],
            "n_events_total": int(len(g)),
            "n_events_significant": int(cfg["sig"](g).sum()),
            "radius_m": RADIUS_M,
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    OUT_JSON.write_text(json.dumps({
        "n_facilities": n,
        "radius_m": RADIUS_M,
        "method": "Poisson event rate: events intersecting a radius buffer "
                  "divided by record length in years",
        "caveat": "SPC records are reports, not a complete census. Report "
                  "density correlates with population and detection capability. "
                  "Significant-event rates are the defensible cross-region "
                  "comparison; all-event rates are restricted to the modern era "
                  "and still carry population bias.",
        "datasets": meta,
    }, indent=2) + "\n")
    print(f"\nWrote {OUT.relative_to(REPO)} ({len(out)} rows, {len(out.columns)} cols)")


if __name__ == "__main__":
    main()
