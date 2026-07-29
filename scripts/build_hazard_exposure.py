"""Build the facility x hazard exposure table.

Reads the final data-center dataset, samples each available hazard layer at every
facility's coordinate, and writes ``data/processed/hazard_exposure.csv`` with one
row per facility and one column per hazard, plus a coverage report.

Hazards are registered in ``HAZARDS`` below. Each entry knows how to produce a
value per facility from a local layer; layers that are not downloaded yet are
skipped with a note (never silently zero-filled). Run from the repo root:

    ./.venv/bin/python scripts/build_hazard_exposure.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from dcdata.hazards.sample import join_polygon_value, sample_raster_at_points

REPO = Path(__file__).resolve().parents[1]
HAZ = REPO / "data" / "hazards" / "data"          # extracted Zenodo archive
HAZ_RAW = REPO / "data" / "hazards"               # layers we download directly
DC_CSV = REPO / "data" / "processed" / "datacenters_final.csv"
OUT_CSV = REPO / "data" / "processed" / "hazard_exposure.csv"


# --- per-hazard samplers -------------------------------------------------------

def haz_lightning(lon, lat):
    """NASA LIS/OTD annual flash climatology (flashes / km2 / yr)."""
    tif = HAZ / "hotspots" / "lightning_annual_rate_4326.tif"
    if not tif.exists():
        return None
    return sample_raster_at_points(tif, lon, lat)


def haz_seismic_pga(lon, lat):
    """USGS NSHM 2023 PGA, 10% in 50 yr (~475-yr return), site class BC, in g.

    Stored as contour-band polygons; a facility takes its band's midpoint PGA.
    """
    shp = HAZ_RAW / "seismic" / "pga_bc" / "US_PGA_10Pct50Yrs_BC_poly.shp"
    if not shp.exists():
        return None
    return join_polygon_value(
        lon, lat, shp,
        value_fn=lambda g: (g["low_cont"].astype(float) + g["high_cont"].astype(float)) / 2.0,
        nodata_mask_fn=lambda g: g["low_cont"].astype(float) <= -1e6,
        fill_nearest=True,
    )


# name -> (column, sampler, units)
HAZARDS = {
    "lightning": ("haz_lightning_flash_per_km2_yr", haz_lightning, "flashes/km2/yr"),
    "seismic":   ("haz_seismic_pga_g_475yr",        haz_seismic_pga, "g (PGA, 10%/50yr, BC)"),
}


def main() -> None:
    dc = pd.read_csv(DC_CSV, low_memory=False)
    lon = dc["longitude"].astype(float).to_numpy()
    lat = dc["latitude"].astype(float).to_numpy()

    out = dc[["facility_id", "name", "operator_company", "state", "county",
              "latitude", "longitude"]].copy()

    print(f"Facilities: {len(dc)}\n")
    report = []
    for key, (col, fn, units) in HAZARDS.items():
        vals = fn(lon, lat)
        if vals is None:
            print(f"  [skip] {key:10s} layer not present locally")
            report.append((key, col, "layer missing", ""))
            continue
        out[col] = vals
        n = int(np.isfinite(vals).sum())
        cov = 100.0 * n / len(vals)
        med = np.nanmedian(vals)
        print(f"  [ok]   {key:10s} -> {col:32s} coverage {n}/{len(vals)} ({cov:.1f}%)  median {med:.3g} {units}")
        report.append((key, col, f"{cov:.1f}%", f"median {med:.3g} {units}"))

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)
    print(f"\nWrote {OUT_CSV.relative_to(REPO)}  ({len(out)} rows, {len(out.columns)} cols)")


if __name__ == "__main__":
    main()
