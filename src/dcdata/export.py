"""Export facilities to CSV + GeoPackage and write a data-quality report.

Outputs (in ``data/processed/``):
  * ``datacenters_all.csv``       — full collection (everything collected)
  * ``datacenters_conus.csv``     — curated view: included & in CONUS
  * ``datacenters_non_conus.csv`` — AK/HI/territory rows (kept, not dropped)
  * ``datacenters.gpkg``          — curated CONUS layer for GIS work
  * ``data_quality_report.md``    — counts + sanity checks
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from dcdata.schema import Facility
from dcdata.validate.checks import looks_lat_lon_swapped, power_in_range


def _flatten(f: Facility) -> dict:
    """Facility -> flat row; provenance rolled up into one JSON column."""
    d = f.model_dump(mode="json")
    sources = d.pop("sources", [])
    d["sources_json"] = json.dumps(sources)
    d["source_name"] = sources[0]["source_name"] if sources else None
    d["source_url"] = sources[0]["source_url"] if sources else None
    d["n_sources"] = len(sources)
    return d


def to_dataframe(facilities: list[Facility]) -> pd.DataFrame:
    return pd.DataFrame([_flatten(f) for f in facilities])


def to_geodataframe(facilities: list[Facility]) -> gpd.GeoDataFrame:
    df = to_dataframe(facilities)
    geometry = [Point(lon, lat) for lon, lat in zip(df["longitude"], df["latitude"])]
    return gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")


def export_dataset(facilities: list[Facility], outdir: Path) -> dict:
    """Write all output files and return a stats dict."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    df = to_dataframe(facilities)

    df.to_csv(outdir / "datacenters_all.csv", index=False)
    curated = df[(df["included"]) & (df["in_conus"])]
    curated.to_csv(outdir / "datacenters_conus.csv", index=False)
    df[~df["in_conus"]].to_csv(outdir / "datacenters_non_conus.csv", index=False)

    curated_facilities = [f for f in facilities if f.included and f.in_conus]
    if curated_facilities:
        gdf = to_geodataframe(curated_facilities)
        gdf.to_file(outdir / "datacenters.gpkg", layer="datacenters", driver="GPKG")

    return {
        "total_collected": len(df),
        "curated_conus": int(len(curated)),
        "non_conus": int((~df["in_conus"]).sum()),
        "excluded_minor": int((df["facility_type"] == "excluded_minor").sum()),
    }


def write_quality_report(facilities: list[Facility], path: Path, stats: dict) -> None:
    """Write a markdown data-quality report with counts and sanity checks."""
    df = to_dataframe(facilities)
    lines: list[str] = ["# Data Quality Report", ""]

    lines.append("## Summary")
    for k, v in stats.items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")

    lines.append("## By facility_type")
    for t, n in Counter(df["facility_type"]).most_common():
        lines.append(f"- {t}: {n}")
    lines.append("")

    lines.append("## By status")
    for s, n in Counter(df["status"]).most_common():
        lines.append(f"- {s}: {n}")
    lines.append("")

    lines.append("## Curated CONUS — top 12 states")
    cur = df[(df["included"]) & (df["in_conus"])]
    states = Counter(s for s in cur["state"] if isinstance(s, str) and s)
    for s, n in states.most_common(12):
        lines.append(f"- {s}: {n}")
    lines.append("")

    lines.append("## Completeness (curated CONUS)")
    n = max(len(cur), 1)
    for col in ["name", "operator_company", "state", "address", "zip"]:
        present = int(cur[col].notna().sum())
        lines.append(f"- {col}: {present}/{len(cur)} ({100 * present // n}%)")
    lines.append("")

    lines.append("## Sanity checks (full collection)")
    swapped = sum(looks_lat_lon_swapped(la, lo) for la, lo in zip(df["latitude"], df["longitude"]))
    mw = df["power_capacity_mw"].dropna()
    bad_mw = int(sum(not power_in_range(v) for v in mw))
    missing_required = int(df[["facility_id", "latitude", "longitude"]].isna().any(axis=1).sum())
    lines.append(f"- suspected lat/lon swaps: {swapped}")
    lines.append(f"- rows missing a required field (id/lat/lon): {missing_required}")
    lines.append(f"- implausible MW values: {bad_mw} (of {len(mw)} with power data)")
    lines.append("")

    Path(path).write_text("\n".join(lines))
