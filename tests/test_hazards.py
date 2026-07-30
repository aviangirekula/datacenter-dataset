"""Unit tests for hazard sampling.

These lock the behaviour that published numbers depend on: nodata and
out-of-bounds must become NaN (never 0), CRS reprojection must be correct
(a lon/lat vs x/y swap would put every facility in the wrong pixel), legitimate
zeros must survive, and polygon imputation must be opt-in, distance-capped and
reported.
"""
from __future__ import annotations

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")

from affine import Affine  # noqa: E402  (comes with rasterio)

from dcdata.hazards.sample import (  # noqa: E402
    join_polygon_value,
    sample_raster_at_points,
    sample_raster_in_buffer,
)


def _write_raster(path, array, crs, transform, nodata=None, dtype="float32"):
    with rasterio.open(
        path, "w", driver="GTiff", height=array.shape[0], width=array.shape[1],
        count=1, dtype=dtype, crs=crs, transform=transform, nodata=nodata,
    ) as dst:
        dst.write(np.asarray(array, dtype=dtype), 1)
    return path


@pytest.fixture
def wgs84_raster(tmp_path):
    """2x2 raster covering lon 0..2, lat 0..2, one pixel flagged nodata."""
    arr = np.array([[1.0, 2.0], [3.0, -9999.0]])
    t = Affine.translation(0, 2) * Affine.scale(1, -1)
    return _write_raster(tmp_path / "w.tif", arr, "EPSG:4326", t, nodata=-9999.0)


def test_known_pixel_values(wgs84_raster):
    # Pixel centres: (0.5,1.5)->1, (1.5,1.5)->2, (0.5,0.5)->3
    got = sample_raster_at_points(wgs84_raster, [0.5, 1.5, 0.5], [1.5, 1.5, 0.5])
    assert got.tolist() == [1.0, 2.0, 3.0]


def test_nodata_becomes_nan_not_zero(wgs84_raster):
    got = sample_raster_at_points(wgs84_raster, [1.5], [0.5])
    assert np.isnan(got[0]), "nodata must be NaN, never 0"


def test_out_of_bounds_becomes_nan(wgs84_raster):
    got = sample_raster_at_points(wgs84_raster, [-5.0, 99.0], [1.0, 1.0])
    assert np.isnan(got).all()


def test_exact_upper_edge_is_not_fabricated(wgs84_raster):
    """A point exactly on the right/bottom bound is outside the grid.

    Regression: inclusive bounds plus rasterio's `nodata or 0` fill silently
    returned 0.0 for such points.
    """
    got = sample_raster_at_points(wgs84_raster, [2.0], [0.0])
    assert np.isnan(got[0])


def test_legitimate_zero_survives(tmp_path):
    """A real 0 must not be nulled (matters for flood depth, where 0 is valid)."""
    arr = np.zeros((2, 2))
    t = Affine.translation(0, 2) * Affine.scale(1, -1)
    p = _write_raster(tmp_path / "z.tif", arr, "EPSG:4326", t, nodata=None)
    got = sample_raster_at_points(p, [0.5], [1.5])
    assert got[0] == 0.0


def test_sentinel_is_per_layer_not_global(tmp_path):
    arr = np.array([[-5.0e6, 7.0], [1.0, 2.0]])
    t = Affine.translation(0, 2) * Affine.scale(1, -1)
    p = _write_raster(tmp_path / "s.tif", arr, "EPSG:4326", t, nodata=None)
    # Without an explicit sentinel the large negative value is preserved.
    assert sample_raster_at_points(p, [0.5], [1.5])[0] == pytest.approx(-5.0e6)
    # With one, it is nulled.
    assert np.isnan(sample_raster_at_points(p, [0.5], [1.5], sentinel_below=-1e6)[0])


def test_reprojection_from_wgs84_to_albers(tmp_path):
    """Points given in lon/lat must land in the right pixel of a 5070 raster.

    This is the highest-risk path: an axis-order slip would misplace every
    facility. Uses a real CONUS location (Ashburn, VA).
    """
    from pyproj import Transformer

    lon, lat = -77.4875, 39.0437
    tr = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
    x, y = tr.transform(lon, lat)

    # 3x3 grid of 270 m pixels centred on that projected coordinate.
    res = 270.0
    t = Affine.translation(x - 1.5 * res, y + 1.5 * res) * Affine.scale(res, -res)
    arr = np.array([[10, 11, 12], [13, 99, 15], [16, 17, 18]], dtype="float32")
    p = _write_raster(tmp_path / "a.tif", arr, "EPSG:5070", t)

    got = sample_raster_at_points(p, [lon], [lat])
    assert got[0] == 99.0, "reprojected point must hit the centre pixel"


def test_buffer_stats_collect_surrounding_pixels(tmp_path):
    from pyproj import Transformer

    lon, lat = -77.4875, 39.0437
    tr = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
    x, y = tr.transform(lon, lat)
    res = 100.0
    t = Affine.translation(x - 2.5 * res, y + 2.5 * res) * Affine.scale(res, -res)
    arr = np.full((5, 5), 6.0, dtype="float32")
    arr[0, 0] = 5.0  # a High-severity pixel in the corner
    p = _write_raster(tmp_path / "b.tif", arr, "EPSG:5070", t)

    # Small radius sees only the centre; large radius reaches the corner.
    near = sample_raster_in_buffer(p, [lon], [lat], radius_m=120)
    far = sample_raster_in_buffer(p, [lon], [lat], radius_m=400)
    assert 5.0 not in near["values"][0].tolist()
    assert 5.0 in far["values"][0].tolist()
    assert far["n"][0] > near["n"][0]


def test_buffer_requires_projected_crs(wgs84_raster):
    with pytest.raises(ValueError, match="projected CRS"):
        sample_raster_in_buffer(wgs84_raster, [0.5], [1.5], radius_m=100)


def test_buffer_is_a_circle_centred_on_the_point_not_the_window(tmp_path):
    """The disc must be centred on the facility and must be round, not square.

    Regression for two distinct bugs: (a) centring the mask on the array index
    centre, which displaces the disc by up to half a pixel per axis once
    rasterio rounds a fractional window offset, and (b) using the whole square
    window instead of the inscribed circle.
    """
    from pyproj import Transformer

    lon, lat = -77.4875, 39.0437
    tr = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
    x, y = tr.transform(lon, lat)

    res = 100.0
    # Deliberately offset the grid origin by a third of a pixel so the point is
    # NOT at a pixel centre and the window offset is fractional.
    t = Affine.translation(x - 10 * res - res / 3, y + 10 * res + res / 3) \
        * Affine.scale(res, -res)
    arr = np.zeros((21, 21), dtype="float32")
    p = _write_raster(tmp_path / "c.tif", arr, "EPSG:5070", t)

    r = 500.0
    got = sample_raster_in_buffer(p, [lon], [lat], radius_m=r)
    n = int(got["n"][0])

    # A circle of radius r on a res-grid holds about pi*r^2/res^2 pixels.
    expected = np.pi * r**2 / res**2
    assert abs(n - expected) / expected < 0.10, (
        f"got {n} pixels, expected ~{expected:.0f} for a circle; "
        "a square window would give ~"
        f"{(2 * r / res) ** 2:.0f}"
    )
    # And must be clearly fewer than the enclosing square.
    assert n < (2 * r / res) ** 2 * 0.85


@pytest.mark.parametrize("frac", [0.3, 0.7, 0.5, 0.0])
def test_buffer_disc_is_centred_on_the_true_point(tmp_path, frac):
    """The disc's centre of mass must sit on the facility, not on the window.

    Each pixel carries its own column index as its value, so the mean of the
    sampled values locates the disc centre in pixel space. For a disc centred on
    a point at fractional column ``fcol``, that mean is ``fcol - 0.5``.

    ``frac`` is swept because the bug this guards (centring on the array index
    centre after rasterio rounds a fractional window offset) cancels out when
    the point happens to land on a pixel boundary or centre. A test fixed at one
    alignment silently passes.
    """
    from pyproj import Transformer

    lon, lat = -77.4875, 39.0437
    tr = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
    x, y = tr.transform(lon, lat)

    res = 100.0
    fcol = frow = 12.0 + frac
    t = Affine.translation(x - fcol * res, y + frow * res) * Affine.scale(res, -res)

    n = 30
    arr = np.tile(np.arange(n, dtype="float32"), (n, 1))  # value == column index
    p = _write_raster(tmp_path / f"ctr{frac}.tif", arr, "EPSG:5070", t)

    vals = sample_raster_in_buffer(p, [lon], [lat], radius_m=500)["values"][0]
    assert vals.size > 50
    got = float(vals.mean())
    expected = fcol - 0.5
    assert abs(got - expected) < 0.12, (
        f"disc centre is at column {got:.3f}, expected {expected:.3f} "
        f"(offset {abs(got - expected) * res:.0f} m at frac={frac})"
    )


# --- polygon join --------------------------------------------------------------

@pytest.fixture
def bands(tmp_path):
    """Two adjacent contour bands plus one sentinel no-data polygon.

    Placed over CONUS so that distances projected into EPSG:5070 are physically
    meaningful (the ``max_fill_m`` cap is expressed in metres).
    """
    gpd = pytest.importorskip("geopandas")
    from shapely.geometry import box

    g = gpd.GeoDataFrame(
        {
            "low_cont": [0.10, 0.20, -1_000_000.0],
            "high_cont": [0.11, 0.21, -1_000_000.0],
            "geometry": [
                box(-100, 40, -99, 41),   # band A
                box(-99, 40, -98, 41),    # band B, adjacent
                box(-90, 40, -89, 41),    # documented no-data region
            ],
        },
        crs="EPSG:4326",
    )
    p = tmp_path / "bands.gpkg"
    g.to_file(p, driver="GPKG")
    return p


def _mid(g):
    return (g["low_cont"].astype(float) + g["high_cont"].astype(float)) / 2.0


def _sentinel(g):
    return g["low_cont"].astype(float) <= -1e6


def test_point_in_polygon_value_and_method(bands):
    r = join_polygon_value([-99.5, -98.5], [40.5, 40.5], bands, _mid, _sentinel)
    assert r["value"] == pytest.approx([0.105, 0.205])
    assert r["method"].tolist() == [1, 1]


def test_no_silent_imputation_by_default(bands):
    """A point far outside every band must be NaN unless fill is requested."""
    r = join_polygon_value([-80.0], [30.0], bands, _mid, _sentinel)
    assert np.isnan(r["value"][0])
    assert r["method"][0] == 0


def test_nearest_fill_is_opt_in_capped_and_flagged(bands):
    # ~85 m east of band B's edge (0.001 deg lon at 40 N).
    lon, lat = [-97.999], [40.5]

    far = join_polygon_value(lon, lat, bands, _mid, _sentinel,
                             fill_nearest=True, max_fill_m=1.0)
    assert np.isnan(far["value"][0]), "beyond max_fill_m must stay NaN"

    near = join_polygon_value(lon, lat, bands, _mid, _sentinel,
                              fill_nearest=True, max_fill_m=5_000)
    assert near["value"][0] == pytest.approx(0.205), "should take band B's value"
    assert near["method"][0] == 2, "imputed values must be flagged as method 2"


def test_documented_nodata_region_is_never_backfilled(bands):
    """Inside the sentinel polygon the answer is 'unknown', not a neighbour's value."""
    r = join_polygon_value([-89.5], [40.5], bands, _mid, _sentinel,
                           fill_nearest=True, max_fill_m=1_000_000)
    assert np.isnan(r["value"][0])
    assert r["method"][0] == 0


def test_fill_nearest_defaults_to_off(bands):
    """A point WELL INSIDE the default fill radius must still be NaN by default.

    Regression: an earlier default of True would silently impute. The point is
    ~85 m outside band B, i.e. inside any plausible cap, so this fails loudly if
    the default flips.
    """
    r = join_polygon_value([-97.999], [40.5], bands, _mid, _sentinel)
    assert np.isnan(r["value"][0]), "imputation must be opt-in"
    assert r["method"][0] == 0


def test_invalid_geometry_is_repaired_before_join(tmp_path):
    """Self-intersecting rings make `within` undefined; they must be repaired."""
    gpd = pytest.importorskip("geopandas")
    from shapely.geometry import Polygon

    # Bow-tie: self-intersecting, invalid.
    bowtie = Polygon([(-100, 40), (-99, 41), (-100, 41), (-99, 40)])
    assert not bowtie.is_valid

    g = gpd.GeoDataFrame(
        {"low_cont": [0.10], "high_cont": [0.11], "geometry": [bowtie]},
        crs="EPSG:4326",
    )
    p = tmp_path / "bad.gpkg"
    g.to_file(p, driver="GPKG")

    # The bow-tie self-intersects at (-99.5, 40.5), leaving a lower lobe with
    # apex there and base along y = 40. This point sits inside that lobe.
    r = join_polygon_value([-99.7], [40.1], p, _mid)
    assert r["value"][0] == pytest.approx(0.105)
    assert r["method"][0] == 1
