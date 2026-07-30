"""Core spatial-sampling helpers for hazard exposure.

Three access patterns cover the hazard layers we use:

* ``sample_raster_at_points`` - point value from a continuous or classified
  raster (lightning flash rate, wildfire hazard class).
* ``sample_raster_in_buffer`` - zonal statistics in a radius around each point.
  Required where the hazard to a *structure* is driven by its surroundings
  rather than by the pixel under the slab (wildfire / wildland-urban interface).
* ``join_polygon_value`` - value of the polygon a point falls inside, for
  hazards published as contour or zone polygons (USGS seismic PGA).

Facility coordinates are always WGS84 (EPSG:4326) lon/lat in this dataset.

Design rules, because these feed a publication:
- Nodata and out-of-bounds always become NaN. Nothing is silently zero-filled.
- Imputation is opt-in (``fill_nearest`` defaults to False), distance-capped,
  measured in metres (not degrees), and reported back to the caller so the
  output can flag imputed values.
- Every function returns provenance alongside values where imputation is
  possible, so "coverage" can be split into measured vs imputed.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

WGS84 = "EPSG:4326"
# Albers Equal Area CONUS - metres. Used for any distance/area computation.
EQUAL_AREA = "EPSG:5070"


def sample_raster_at_points(
    raster_path: str | Path,
    lon: np.ndarray,
    lat: np.ndarray,
    band: int = 1,
    sentinel_below: float | None = None,
) -> np.ndarray:
    """Return the raster value under each (lon, lat) point, NaN where unknown.

    Points are supplied in WGS84 and reprojected into the raster CRS. Masked
    (nodata) pixels and points outside the raster become ``np.nan``.

    ``sentinel_below`` optionally nulls values at or below a per-layer sentinel
    (e.g. -1e6 in some USGS products). It is per-layer on purpose: applying a
    global rule would destroy legitimate large-negative values in future layers
    such as elevation differentials.
    """
    import rasterio
    from pyproj import Transformer

    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)
    out = np.full(len(lon), np.nan, dtype=float)

    with rasterio.open(raster_path) as src:
        if src.crs is not None and src.crs.to_string() not in (WGS84, "EPSG:4326"):
            tr = Transformer.from_crs(WGS84, src.crs, always_xy=True)
            xs, ys = tr.transform(lon, lat)
        else:
            xs, ys = lon, lat

        # Exclusive on the upper/right edge: a point exactly on `right`/`bottom`
        # is outside the pixel grid, and rasterio would return its nodata-or-0
        # fill for it.
        left, bottom, right, top = src.bounds
        ok = (xs >= left) & (xs < right) & (ys > bottom) & (ys <= top)
        ok &= np.isfinite(xs) & np.isfinite(ys)
        if not ok.any():
            return out

        coords = [(x, y) for x, y in zip(np.asarray(xs)[ok], np.asarray(ys)[ok])]
        # masked=True gives an explicit nodata mask instead of float comparison.
        rows = list(src.sample(coords, indexes=band, masked=True))

    vals = np.array(
        [np.nan if np.ma.is_masked(r[0]) else float(r[0]) for r in rows],
        dtype=float,
    )
    if sentinel_below is not None:
        vals = np.where(vals <= sentinel_below, np.nan, vals)
    out[ok] = vals
    return out


def sample_raster_in_buffer(
    raster_path: str | Path,
    lon: np.ndarray,
    lat: np.ndarray,
    radius_m: float,
    band: int = 1,
) -> dict[str, np.ndarray]:
    """Zonal statistics for a circular buffer around each point.

    Reads a square window of side ``2 * radius_m`` around each point (in the
    raster's own CRS, which must be projected in metres) and masks it to the
    inscribed circle. Returns arrays keyed by statistic:

    ``values``  list-like object array of the in-circle pixel values per point
    ``n``       number of valid pixels considered

    Callers derive layer-specific statistics (class fractions, max severity)
    from ``values`` so this helper stays hazard-agnostic.
    """
    import rasterio
    from pyproj import Transformer
    from rasterio.windows import from_bounds

    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)
    n_pts = len(lon)
    values: list[np.ndarray] = [np.array([], dtype=float)] * n_pts
    counts = np.zeros(n_pts, dtype=int)

    with rasterio.open(raster_path) as src:
        if src.crs is None:
            raise ValueError(f"{raster_path} has no CRS; cannot buffer in metres")
        if not src.crs.is_projected:
            raise ValueError(
                f"{raster_path} is geographic ({src.crs}); buffering needs a "
                "projected CRS in metres"
            )
        tr = Transformer.from_crs(WGS84, src.crs, always_xy=True)
        xs, ys = tr.transform(lon, lat)
        px, py = src.res

        for i, (x, y) in enumerate(zip(xs, ys)):
            if not (np.isfinite(x) and np.isfinite(y)):
                continue
            win = from_bounds(
                x - radius_m, y - radius_m, x + radius_m, y + radius_m,
                transform=src.transform,
            )
            try:
                arr = src.read(band, window=win, masked=True, boundless=True)
            except Exception:
                continue
            if arr.size == 0:
                continue

            # Mask to the inscribed circle using pixel-centre distances.
            h, w = arr.shape
            gy, gx = np.mgrid[0:h, 0:w]
            cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
            dist = np.sqrt(((gx - cx) * px) ** 2 + ((gy - cy) * py) ** 2)
            circle = dist <= radius_m

            sel = arr[circle & ~np.ma.getmaskarray(arr)]
            vals = np.asarray(sel, dtype=float).ravel()
            values[i] = vals
            counts[i] = vals.size

    return {"values": np.array(values, dtype=object), "n": counts}


def join_polygon_value(
    lon: np.ndarray,
    lat: np.ndarray,
    poly_path: str | Path,
    value_fn,
    nodata_mask_fn=None,
    fill_nearest: bool = False,
    max_fill_m: float = 25_000.0,
) -> dict[str, np.ndarray]:
    """Assign each point the value of the polygon it falls in.

    ``value_fn(gdf) -> Series`` computes the scalar hazard value per polygon
    (e.g. the midpoint of a PGA contour band). ``nodata_mask_fn(gdf)`` marks
    polygons that represent *documented no-data* regions; points inside them are
    forced to NaN and are never back-filled from a neighbour.

    ``fill_nearest`` is opt-in. When enabled, points matching no polygon take the
    nearest polygon's value **only** within ``max_fill_m`` metres, measured in an
    equal-area projected CRS (not degrees).

    Returns ``{"value", "method"}`` where ``method`` is 0 = no data,
    1 = point-in-polygon, 2 = nearest-filled. This lets the caller report
    measured versus imputed coverage separately.
    """
    import geopandas as gpd
    from shapely.geometry import Point

    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)

    g = gpd.read_file(poly_path)
    if g.crs is None:
        g = g.set_crs(WGS84)
    g = g.to_crs(WGS84).copy()
    # Self-intersecting rings make `within` undefined; repair before joining.
    invalid = ~g.geometry.is_valid
    if bool(invalid.any()):
        g.loc[invalid, "geometry"] = g.loc[invalid, "geometry"].make_valid()

    g["_value"] = np.asarray(value_fn(g), dtype=float)

    nodata_g = None
    if nodata_mask_fn is not None:
        mask = np.asarray(nodata_mask_fn(g), dtype=bool)
        nodata_g = g[mask]
        g = g[~mask]
    g = g[np.isfinite(g["_value"])].reset_index(drop=True)

    pts = gpd.GeoDataFrame(
        {"_i": np.arange(len(lon))},
        geometry=[Point(x, y) for x, y in zip(lon, lat)],
        crs=WGS84,
    )

    joined = gpd.sjoin(pts, g[["_value", "geometry"]], how="left", predicate="within")
    # Contour bands should partition space; overlaps are topology slivers. Taking
    # the max is conservative, and n_multi surfaces any genuinely nested layer.
    n_multi = int((joined.groupby("_i").size() > 1).sum())
    vals = joined.groupby("_i")["_value"].max().reindex(range(len(lon)))
    value = vals.to_numpy(dtype=float, copy=True)

    method = np.where(np.isfinite(value), 1, 0).astype(int)

    if fill_nearest and (~np.isfinite(value)).any():
        missing = np.where(~np.isfinite(value))[0]
        # Distances must be metric: project both frames to equal-area.
        pts_m = pts.iloc[missing].to_crs(EQUAL_AREA)
        g_m = g[["_value", "geometry"]].to_crs(EQUAL_AREA)
        near = gpd.sjoin_nearest(
            pts_m, g_m, how="left", max_distance=max_fill_m, distance_col="_dist"
        )
        near = near[np.isfinite(near["_value"])]
        if len(near):
            picked = near.sort_values("_dist").groupby("_i").first()
            for i, row in picked.iterrows():
                value[int(i)] = float(row["_value"])
                method[int(i)] = 2

    # Documented no-data polygons win over any fill.
    if nodata_g is not None and len(nodata_g):
        inside_nd = gpd.sjoin(
            pts, nodata_g[["geometry"]], how="inner", predicate="within"
        )["_i"].to_numpy()
        if inside_nd.size:
            value[inside_nd] = np.nan
            method[inside_nd] = 0

    return {"value": value, "method": method, "n_multi_match": n_multi}
