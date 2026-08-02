"""Per-facility severe-storm exposure from NOAA SPC event records.

Tornado, hail and damaging wind are published as historical event reports rather
than hazard surfaces, so exposure has to be estimated. Three quantities are
produced, and it matters which one is used for what.

**1. Areal event-day density** (``*_density_per_10k_km2_yr``). Event-days within
a radius, divided by the disc area and the record length. This is a *regional
climatological density*, not a facility-specific quantity: a 40 km disc puts 44%
of its area in the outer 30-40 km annulus, so the value describes the region
around the facility rather than the site. Reported with exact Poisson 95%
intervals because the underlying counts are small.

**2. Tornado point-strike probability** (``tornado_strike_prob_per_yr``). Sum of
damage-path areas (length x width) of tornado tracks intersecting the disc,
divided by the disc area and the record length. This is the classical
Thom/Schaefer path-area estimator and is the defensible *site* quantity. It is
roughly three orders of magnitude smaller than the disc count, which is the
point: a disc count of 0.19/yr does not mean a tornado hits the site every five
years.

**3. Event-days, not reports.** A single storm day contributes ~2.8 hail or wind
reports, and that multiplier tracks spotter density rather than weather. Counting
distinct dates removes most of it.

REPORTING BIAS IS NOT FULLY CONTROLLED, and this is stated rather than claimed
away. Testing the record directly: significant hail reports rose 24% per decade
and significant wind 26% per decade even within 1996-2024, so a
significant-event threshold does **not** make the series stationary. Only EF2+
tornado is approximately stationary. Mitigations actually applied:

- a single modern window (2000-2024) for every hazard, so no two columns carry
  different denominators,
- event-days rather than raw reports,
- explicit removal of magnitude sentinels (wind ``mag == 0`` is a missing-value
  code covering 21% of the full record and 60-72% of pre-2000 decades, not a
  calm-wind observation),
- per-facility Poisson confidence intervals so thinly-sampled sites are visibly
  uncertain.

Residual bias remains correlated with population density. Cross-region
comparisons should be read with that caveat, and a radar-derived product
(MESH for hail) or a published smoothed climatology is the better long-term
source.

    ./.venv/bin/python scripts/build_storm_exposure.py
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import chi2

REPO = Path(__file__).resolve().parents[1]
DC_CSV = REPO / "data" / "processed" / "datacenters_final.csv"
STORM_DIR = REPO / "data" / "hazards" / "storms"
IBTRACS = (REPO / "data" / "hazards" / "hurricane"
           / "IBTrACS.NA.list.v04r01.points.shp")
OUT = REPO / "data" / "processed" / "storm_exposure.csv"
OUT_JSON = REPO / "data" / "processed" / "storm_exposure_coverage.json"

EQUAL_AREA = "EPSG:5070"
RADIUS_M = 40_000.0
DISC_KM2 = np.pi * (RADIUS_M / 1000.0) ** 2

# One window for every hazard. 2000 clears the worst of the wind magnitude
# sentinel era and sits after the 1990s radar rollout.
YEAR_FROM, YEAR_TO = 2000, 2024
YEARS = YEAR_TO - YEAR_FROM + 1

MI_M, YD_M = 1609.344, 0.9144

DATASETS = {
    "tornado": {"dir": "1950-2024-torn-aspath",
                "sig": lambda g: g["mag"] >= 2, "sig_label": "EF2+",
                # -9 marks an unrated tornado, not an F0.
                "valid_mag": lambda g: g["mag"] >= 0},
    "hail": {"dir": "1955-2024-hail-aspath",
             "sig": lambda g: g["mag"] >= 2.0, "sig_label": "2.00 in or larger",
             "valid_mag": lambda g: g["mag"] > 0},
    "wind": {"dir": "1955-2024-wind-aspath",
             "sig": lambda g: g["mag"] >= 65, "sig_label": "65 kt or greater",
             # mag == 0 is a missing-value sentinel, not a calm observation.
             "valid_mag": lambda g: g["mag"] > 0},
}


def poisson_ci(k: np.ndarray, exposure: float) -> tuple[np.ndarray, np.ndarray]:
    """Exact (Garwood) Poisson 95% interval for a count, per unit exposure."""
    k = np.asarray(k, dtype=float)
    lo = np.where(k > 0, chi2.ppf(0.025, 2 * k) / 2.0, 0.0)
    hi = chi2.ppf(0.975, 2 * (k + 1)) / 2.0
    return lo / exposure, hi / exposure


def main() -> None:
    dc = pd.read_csv(DC_CSV, low_memory=False)
    n = len(dc)
    pts = gpd.GeoDataFrame(
        {"_i": np.arange(n)},
        geometry=gpd.points_from_xy(dc["longitude"], dc["latitude"]),
        crs="EPSG:4326").to_crs(EQUAL_AREA)
    buf = pts.copy()
    buf["geometry"] = buf.geometry.buffer(RADIUS_M)

    out = dc[["facility_id", "name", "state", "latitude", "longitude"]].copy()
    meta: dict[str, dict] = {}

    for key, cfg in DATASETS.items():
        shp = STORM_DIR / cfg["dir"] / f"{cfg['dir']}.shp"
        if not shp.exists():
            print(f"  [skip] {key}: missing")
            continue
        print(f"\n{key}: reading ...")
        g = gpd.read_file(shp)
        g = g[g.geometry.notna() & ~g.geometry.is_empty]
        if g.crs is None:
            g = g.set_crs("EPSG:4326")
        g["mag"] = pd.to_numeric(g["mag"], errors="coerce")
        g["yr"] = pd.to_numeric(g["yr"], errors="coerce")

        n_raw = len(g)
        g = g[(g["yr"] >= YEAR_FROM) & (g["yr"] <= YEAR_TO)]
        n_window = len(g)
        g = g[cfg["valid_mag"](g)]
        n_valid = len(g)
        sig = g[cfg["sig"](g)].to_crs(EQUAL_AREA)
        print(f"  {n_raw:,} raw -> {n_window:,} in {YEAR_FROM}-{YEAR_TO} "
              f"-> {n_valid:,} with usable magnitude -> {len(sig):,} significant")

        if len(sig) == 0:
            continue
        sig = sig.reset_index(drop=True)
        sig["_date"] = pd.to_datetime(sig["date"], errors="coerce").dt.date

        j = gpd.sjoin(buf[["_i", "geometry"]], sig[["geometry", "_date"]],
                      how="inner", predicate="intersects")
        # Event-DAYS, not reports: one storm day yields multiple reports and the
        # multiplier tracks observer density.
        days = j.groupby("_i")["_date"].nunique().reindex(range(n), fill_value=0)
        k = days.to_numpy()

        dens = k / (DISC_KM2 * YEARS) * 1e4
        lo, hi = poisson_ci(k, DISC_KM2 * YEARS / 1e4)
        out[f"{key}_event_days"] = k
        out[f"{key}_density_per_10k_km2_yr"] = dens
        out[f"{key}_density_lo95"] = lo
        out[f"{key}_density_hi95"] = hi
        print(f"  density median {np.median(dens):.3f} per 10k km2/yr | "
              f"zero-count facilities {int((k == 0).sum())}")

        meta[key] = {
            "window": f"{YEAR_FROM}-{YEAR_TO}", "years": YEARS,
            "significant_threshold": cfg["sig_label"],
            "n_significant_events": int(len(sig)),
            "facilities_with_zero_events": int((k == 0).sum()),
            "median_density_per_10k_km2_yr": float(np.median(dens)),
        }

        # Tornado only: the path-area point-strike estimator.
        if key == "tornado":
            s = sig.copy()
            s["_area_m2"] = (pd.to_numeric(s["len"], errors="coerce").fillna(0) * MI_M
                             * pd.to_numeric(s["wid"], errors="coerce").fillna(0) * YD_M)
            j2 = gpd.sjoin(buf[["_i", "geometry"]], s[["geometry", "_area_m2"]],
                           how="inner", predicate="intersects")
            swept = j2.groupby("_i")["_area_m2"].sum().reindex(range(n), fill_value=0.0)
            prob = swept.to_numpy() / (DISC_KM2 * 1e6) / YEARS
            out["tornado_strike_prob_per_yr"] = prob
            with np.errstate(divide="ignore"):
                rp = np.where(prob > 0, 1.0 / prob, np.nan)
            out["tornado_strike_return_yr"] = rp
            print(f"  path-area strike prob: median {np.nanmedian(prob):.2e}/yr "
                  f"(return period ~{np.nanmedian(rp):,.0f} yr)")
            meta["tornado"]["strike_estimator"] = (
                "path-area (Thom/Schaefer): sum of track length x width "
                "intersecting the disc, divided by disc area and years")

    # --- tropical cyclone (IBTrACS North Atlantic) -----------------------------
    # Track fixes are 3-hourly points, so exposure is the count of DISTINCT
    # storms (by SID) whose track passes within the radius, not the point count.
    if IBTRACS.exists():
        print("\nhurricane: reading IBTrACS ...")
        tc = gpd.read_file(IBTRACS)
        tc["SEASON"] = pd.to_numeric(tc["SEASON"], errors="coerce")
        tc["USA_SSHS"] = pd.to_numeric(tc["USA_SSHS"], errors="coerce")
        # Satellite era only. Pre-1980 intensities rest on sparser observation
        # and would bias a rate computed over the full 1851 record.
        TC_FROM = 1980
        tc_years = YEAR_TO - TC_FROM + 1
        tc = tc[(tc["SEASON"] >= TC_FROM) & (tc["SEASON"] <= YEAR_TO)]
        # USA_SSHS: negative and 0 are sub-hurricane (disturbance, depression,
        # tropical storm). 1-5 are Saffir-Simpson hurricane categories.
        # Fixes are 3-hourly and a median 58 km apart, with 72% of legs longer
        # than the search radius, so a storm can cross the whole disc between two
        # recorded points. Joining points alone undercounts by ~35%. Build
        # LineString tracks from consecutive fixes instead.
        from shapely.geometry import LineString

        def _tracks(sub: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
            sub = sub.sort_values(["SID", "ISO_TIME"])
            segs, sids = [], []
            for sid, grp in sub.groupby("SID", sort=False):
                pts = [(g.x, g.y) for g in grp.geometry if g is not None]
                if len(pts) >= 2:
                    segs.append(LineString(pts))
                    sids.append(sid)
                elif len(pts) == 1:
                    segs.append(grp.geometry.iloc[0])
                    sids.append(sid)
            return gpd.GeoDataFrame({"SID": sids}, geometry=segs, crs=sub.crs)

        for label, sel in [("tc_named", tc["USA_SSHS"] >= 0),
                           ("tc_hurricane", tc["USA_SSHS"] >= 1),
                           ("tc_major", tc["USA_SSHS"] >= 3)]:
            sub = tc[sel].to_crs(EQUAL_AREA)
            if not len(sub):
                continue
            sub = _tracks(sub)
            j = gpd.sjoin(buf[["_i", "geometry"]], sub[["geometry", "SID"]],
                          how="inner", predicate="intersects")
            k = j.groupby("_i")["SID"].nunique().reindex(range(n), fill_value=0).to_numpy()
            out[f"{label}_storms_per_yr"] = k / tc_years
            lo, hi = poisson_ci(k, tc_years)
            out[f"{label}_lo95"] = lo
            out[f"{label}_hi95"] = hi
            print(f"  {label}: median {np.median(k / tc_years):.3f} storms/yr, "
                  f"max {np.max(k / tc_years):.3f}, "
                  f"facilities with none {int((k == 0).sum())}")
        meta["tropical_cyclone"] = {
            "source": "NOAA IBTrACS v04r01, North Atlantic basin",
            "window": f"{TC_FROM}-{YEAR_TO}", "years": tc_years,
            "unit": "distinct storms whose track passes within the radius, per year",
            "intensity_levels": "tc_named = tropical storm or above (SSHS>=0), "
                                "tc_hurricane = SSHS>=1, tc_major = SSHS>=3",
            "geometry": "consecutive 3-hourly fixes joined into LineString "
                        "tracks per storm; point-only joins undercount by ~35% "
                        "because 72% of legs exceed the search radius",
            "note": "Track proximity is not landfall intensity. A track passing "
                    "within 40 km says the storm came close, not what wind the "
                    "site experienced. ASCE 7 design wind speed is the correct "
                    "measure of design demand.",
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    OUT_JSON.write_text(json.dumps({
        "n_facilities": n, "radius_m": RADIUS_M, "disc_km2": DISC_KM2,
        "window": f"{YEAR_FROM}-{YEAR_TO}",
        "units": {
            "density_per_10k_km2_yr": "regional event-day density, NOT a "
                                      "facility-specific strike rate",
            "tornado_strike_prob_per_yr": "annual probability the facility "
                                          "point is inside a tornado damage path",
        },
        "reporting_bias": "NOT fully controlled. Significant hail and wind "
                          "report counts rise ~24-26% per decade even within "
                          "the modern era, and residual bias correlates with "
                          "population density. Only EF2+ tornado is "
                          "approximately stationary.",
        "datasets": meta,
    }, indent=2) + "\n")
    print(f"\nWrote {OUT.relative_to(REPO)} ({len(out)} rows, {len(out.columns)} cols)")


if __name__ == "__main__":
    main()
