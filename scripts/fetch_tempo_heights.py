"""Sample the Microsoft building density and height layer at each facility.

Source: microsoft/buildings, the TEMPO global building density and height
dataset, released under CDLA Permissive 2.0. Cloud-Optimized GeoTIFFs indexed by
a GeoPackage tile index, two bands per tile:

    band 1  building density, fraction of the pixel covered by buildings
    band 2  building height, normalised 0 to 1, multiply by 100 for metres

**What this is and is not.** It is a deep-learning estimate from 4.7 m Planet
imagery, aggregated to a ~76 m pixel in EPSG:3857. The height is a property of
the pixel, not of a building. A data center footprint is usually smaller than one
pixel, so the value mixes the facility with whatever else shares the cell.

It is therefore NOT a substitute for the USA Structures heights or the 3DEP lidar
measurements, and it is stored in its own columns rather than merged into
height_m. It is kept for two things it is genuinely good for: complete coverage,
including the facilities lidar cannot reach, and an independent cross-check.

    ./.venv/bin/python scripts/fetch_tempo_heights.py
"""
from __future__ import annotations

import os
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
# Without these every COG read tries to list the whole bucket directory.
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")

import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402
import rasterio  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
DC_CSV = REPO / "data" / "processed" / "datacenters_final.csv"
INDEX = REPO / "data" / "raw" / "tempo" / "tile_index.gpkg"
OUT = REPO / "data" / "processed" / "tempo_building_density.csv"
INDEX_URL = "https://opendata.aiforgood.ai/building-density/tile_index.gpkg"
HEIGHT_SCALE = 100.0        # band 2 is normalised 0-1


def main() -> None:
    if not INDEX.exists():
        raise SystemExit(f"tile index missing. Download {INDEX_URL} to {INDEX}")

    dc = pd.read_csv(DC_CSV, low_memory=False)
    idx = gpd.read_file(INDEX)
    pts = gpd.GeoDataFrame(
        dc[["facility_id"]],
        geometry=gpd.points_from_xy(dc["longitude"], dc["latitude"]),
        crs="EPSG:4326").to_crs(idx.crs)
    j = (gpd.sjoin(pts, idx[["data_2023q4", "geometry"]], how="left",
                   predicate="within")
           .drop_duplicates("facility_id"))
    j = j[j["data_2023q4"].notna()]
    print(f"facilities inside a tile: {len(j)}/{len(dc)} | "
          f"tiles to read: {j['data_2023q4'].nunique()}", flush=True)

    rows = []
    tiles = list(j.groupby("data_2023q4"))
    for i, (url, sub) in enumerate(tiles, 1):
        try:
            with rasterio.open("/vsicurl/" + url) as src:
                geo = sub.geometry.to_crs(src.crs)
                vals = list(src.sample([(p.x, p.y) for p in geo], indexes=[1, 2]))
            for fid, v in zip(sub["facility_id"], vals):
                rows.append({"facility_id": fid,
                             "tempo_building_density": float(v[0]),
                             "tempo_height_m": float(v[1]) * HEIGHT_SCALE})
        except Exception as e:  # noqa: BLE001 - one bad tile must not stop the run
            for fid in sub["facility_id"]:
                rows.append({"facility_id": fid, "tempo_building_density": None,
                             "tempo_height_m": None,
                             "error": f"{type(e).__name__}: {e}"[:120]})
        if i % 50 == 0:
            print(f"  {i}/{len(tiles)} tiles", flush=True)

    out = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    got = int(out["tempo_height_m"].notna().sum())
    print(f"wrote {OUT.relative_to(REPO)}  {got}/{len(dc)} sampled")


if __name__ == "__main__":
    main()
