"""Measure how much the storm rates track observer density rather than weather.

NOAA SPC records are *reports*, not a census, so report density rises with
population and with detection capability. The exposure table documents this, but
"bias exists" is not a usable statement for a methods section. This quantifies
it.

Method. Facility density within 40 km is used as a proxy for local population
and observer density. Comparing storm rate against that proxy **across** the
country would mostly measure real climatology (the Plains have both more storms
and fewer people), so the comparison is made **within state**, with both
variables de-meaned by their state median. What survives is the association
between a facility's storm rate and how built-up its surroundings are, holding
regional climatology roughly constant.

A strong positive association means the cross-region comparison is contaminated.
A near-zero one means the metric is defensible.

Fixing this properly needs a radar-derived product such as gridded MESH. That is
not reachable here: a per-facility radar climatology over 25 years would require
roughly 800,000 NCEI queries.

    ./.venv/bin/python scripts/storm_bias_diagnostic.py
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REPO = Path(__file__).resolve().parents[1]
STORM = REPO / "data" / "processed" / "storm_exposure.csv"
OUT = REPO / "data" / "processed" / "storm_bias_diagnostic.json"

EQUAL_AREA = "EPSG:5070"
RADIUS_M = 40_000.0
COLS = {
    "tornado": "tornado_density_per_10k_km2_yr",
    "hail": "hail_density_per_10k_km2_yr",
    "wind": "wind_density_per_10k_km2_yr",
}


def main() -> None:
    s = pd.read_csv(STORM, low_memory=False)
    pts = gpd.GeoDataFrame(
        s[["facility_id", "state"]].copy(),
        geometry=gpd.points_from_xy(s["longitude"], s["latitude"]),
        crs="EPSG:4326").to_crs(EQUAL_AREA)
    pts["_i"] = np.arange(len(pts))

    # Observer-density proxy: how many other facilities share the same 40 km disc.
    buf = pts.copy()
    buf["geometry"] = buf.geometry.buffer(RADIUS_M)
    j = gpd.sjoin(buf[["_i", "geometry"]], pts[["geometry"]],
                  how="inner", predicate="intersects")
    dens = j.groupby("_i").size().reindex(range(len(pts)), fill_value=0) - 1
    s["neighbours_40km"] = dens.to_numpy()

    out: dict = {
        "proxy": "count of other data centers within 40 km, standing in for "
                 "population and observer density",
        "method": "Spearman correlation between storm rate and the proxy, both "
                  "de-meaned by state median, so regional climatology is held "
                  "roughly constant",
        "n_facilities": int(len(s)),
        "hazards": {},
    }

    print(f"facilities: {len(s)} | median neighbours within 40 km: "
          f"{int(np.median(s['neighbours_40km']))}")
    print("\n=== association between storm rate and observer-density proxy ===")
    print("  (raw = across the whole country, within-state = climatology removed)\n")

    for name, col in COLS.items():
        if col not in s.columns:
            continue
        d = s[[col, "neighbours_40km", "state"]].dropna()
        raw = spearmanr(d[col], d["neighbours_40km"])
        # De-mean both variables by state median.
        g = d.groupby("state")
        dc = d[col] - g[col].transform("median")
        dn = d["neighbours_40km"] - g["neighbours_40km"].transform("median")
        within = spearmanr(dc, dn)
        out["hazards"][name] = {
            "column": col,
            "spearman_raw": round(float(raw.statistic), 3),
            "spearman_within_state": round(float(within.statistic), 3),
            "p_within_state": float(within.pvalue),
        }
        flag = ("CONTAMINATED" if abs(within.statistic) >= 0.3
                else "moderate" if abs(within.statistic) >= 0.15 else "weak")
        print(f"  {name:8s} raw {raw.statistic:+.3f} | within-state "
              f"{within.statistic:+.3f} (p={within.pvalue:.1e})  -> {flag}")

    worst = max(out["hazards"].values(),
                key=lambda v: abs(v["spearman_within_state"]), default=None)
    if worst:
        out["conclusion"] = (
            f"Strongest within-state association is "
            f"{worst['spearman_within_state']:+.3f} for {worst['column']}. "
            "Values above about 0.3 mean the rate is partly measuring where "
            "people live rather than where storms occur, so cross-region "
            "comparisons of that hazard should be avoided or explicitly caveated."
        )
        print(f"\n{out['conclusion']}")

    out["fix_requires"] = (
        "A radar-derived gridded product (e.g. MESH-based hail climatology). "
        "Not reachable via the NCEI SWDI point service: a 25-year per-facility "
        "climatology would need roughly 800,000 queries."
    )
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\nWrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
