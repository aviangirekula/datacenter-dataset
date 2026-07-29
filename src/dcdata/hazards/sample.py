"""Core spatial-sampling helpers for hazard exposure.

Two access patterns cover the hazard layers we use:

* ``sample_raster_at_points`` - for continuous raster hazards (lightning flash
  rate, wildfire hazard potential, flood depth). Reprojects the facility points
  into the raster CRS, reads the pixel value under each point, maps nodata and
  out-of-bounds to NaN.
* ``join_polygon_value`` - for hazards stored as contour/zone polygons (USGS
  seismic PGA). Each facility takes the value of the polygon it falls inside;
  points that miss every polygon optionally borrow the nearest polygon's value.

Facility coordinates are always WGS84 (EPSG:4326) lon/lat in this dataset.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

WGS84 = "EPSG:4326"


def sample_raster_at_points(
    raster_path: str | Path,
    lon: np.ndarray,
    lat: np.ndarray,
    band: int = 1,
) -> np.ndarray:
    """Return the raster value under each (lon, lat) point.

    Points are given in WGS84. They are reprojected to the raster's own CRS
    before sampling. Nodata pixels and points outside the raster footprint come
    back as ``np.nan``.
    """
    import rasterio
    from pyproj import Transformer

    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)

    with rasterio.open(raster_path) as src:
        # Reproject points WGS84 -> raster CRS if needed.
        if src.crs is not None and src.crs.to_string() not in (WGS84, "EPSG:4326"):
            tr = Transformer.from_crs(WGS84, src.crs, always_xy=True)
            xs, ys = tr.transform(lon, lat)
        else:
            xs, ys = lon, lat

        left, bottom, right, top = src.bounds
        in_bounds = (xs >= left) & (xs <= right) & (ys >= bottom) & (ys <= top)

        out = np.full(len(lon), np.nan, dtype=float)
        coords = [(x, y) for x, y in zip(xs, ys)]
        vals = np.array([v[band - 1] for v in src.sample(coords, indexes=band)], dtype=float)

        nodata = src.nodata
        if nodata is not None:
            vals = np.where(vals == nodata, np.nan, vals)
        # NSHM-style sentinel for "no data" that some layers use.
        vals = np.where(vals <= -1e6, np.nan, vals)
        out[in_bounds] = vals[in_bounds]
        return out


def join_polygon_value(
    lon: np.ndarray,
    lat: np.ndarray,
    poly_path: str | Path,
    value_fn,
    nodata_mask_fn=None,
    fill_nearest: bool = True,
) -> np.ndarray:
    """Assign each point the value of the polygon it falls in.

    ``value_fn(gdf) -> Series`` computes the scalar hazard value for every
    polygon row (e.g. midpoint of a PGA contour band). ``nodata_mask_fn(gdf)``
    optionally returns a boolean Series marking polygons to drop (ocean, sentinel
    values). When ``fill_nearest`` is True, points that land in no polygon take
    the value of the nearest remaining polygon.
    """
    import geopandas as gpd
    from shapely.geometry import Point

    g = gpd.read_file(poly_path)
    if g.crs is None:
        g = g.set_crs(WGS84)
    g = g.to_crs(WGS84)

    g = g.copy()
    g["_value"] = np.asarray(value_fn(g), dtype=float)
    if nodata_mask_fn is not None:
        g = g[~np.asarray(nodata_mask_fn(g), dtype=bool)]
    g = g[np.isfinite(g["_value"])].reset_index(drop=True)

    pts = gpd.GeoDataFrame(
        {"_i": np.arange(len(lon))},
        geometry=[Point(x, y) for x, y in zip(lon, lat)],
        crs=WGS84,
    )

    joined = gpd.sjoin(pts, g[["_value", "geometry"]], how="left", predicate="within")
    # If a point falls in overlapping bands, keep the highest value (conservative).
    vals = joined.groupby("_i")["_value"].max().reindex(range(len(lon)))
    out = vals.to_numpy(dtype=float)

    if fill_nearest and np.isnan(out).any():
        missing = np.where(np.isnan(out))[0]
        near = gpd.sjoin_nearest(pts.iloc[missing], g[["_value", "geometry"]], how="left")
        near_vals = near.groupby("_i")["_value"].max()
        for i, v in near_vals.items():
            out[i] = v
    return out
