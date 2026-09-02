"""Build the facility x hazard exposure table.

Reads the final data-center dataset, samples each available hazard layer at
every facility, and writes:

- ``data/processed/hazard_exposure.csv``      one row per facility
- ``data/processed/hazard_exposure_coverage.json``  machine-readable coverage

Coverage is split into *measured* versus *imputed* so a reader never has to take
a "100%" figure on trust. Positional-accuracy fields are carried through from the
facility dataset so downstream analysis can restrict to building-verified
coordinates.

Run from the repo root:

    ./.venv/bin/python scripts/build_hazard_exposure.py
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from dcdata.hazards.sample import (
    join_polygon_value,
    sample_raster_at_points,
    sample_raster_in_buffer,
)

REPO = Path(__file__).resolve().parents[1]
HAZ = REPO / "data" / "hazards" / "data"          # extracted Zenodo archive
HAZ_RAW = REPO / "data" / "hazards"               # layers downloaded directly
DC_CSV = REPO / "data" / "processed" / "datacenters_final.csv"
OUT_CSV = REPO / "data" / "processed" / "hazard_exposure.csv"
OUT_JSON = REPO / "data" / "processed" / "hazard_exposure_coverage.json"
# Authoritative per-point seismic values from the USGS ASCE 7-22 service.
SEISMIC_POINTS = REPO / "data" / "raw" / "seismic_points_multilevel.jsonl"
SEISMIC_NSHM = REPO / "data" / "raw" / "seismic_nshm_curves.jsonl"

# Positional-accuracy fields carried into the exposure table. Hazard values are
# only as good as the coordinate they were sampled at.
CARRY = [
    "facility_id", "name", "operator_company", "facility_type", "status",
    "state", "county", "latitude", "longitude",
    "coordinate_precision", "verification_status", "coord_confidence",
    "size_sqft", "num_floors",
]

LIGHTNING_TIF = HAZ / "hotspots" / "lightning_annual_rate_4326.tif"
WHP_TIF = HAZ_RAW / "wildfire" / "whp" / "Data" / "whp2023_GeoTIF" / "whp2023_cls_conus.tif"
SEISMIC_DIR = HAZ_RAW / "seismic" / "pga_bc"

# USGS NSHM 2023 uniform-hazard maps. Probability of exceedance in 50 years ->
# approximate mean return period.
SEISMIC_LEVELS = {
    "10Pct": 475,
    "5Pct": 975,
    "2Pct": 2475,
}

# USFS WHP class codes. 1-5 are an ordinal severity ladder; 6 and 7 are NOMINAL
# surface categories and must never be averaged or ranked against 1-5.
WHP_SEVERITY = {1: "very_low", 2: "low", 3: "moderate", 4: "high", 5: "very_high"}
WHP_NONBURNABLE = 6
WHP_WATER = 7
# Buffer radii for wildland-urban-interface style statistics.
WHP_RADII_M = (1_000, 2_400, 5_000)


def _git_sha() -> str:
    """Short HEAD SHA, suffixed '-dirty' if the worktree has uncommitted changes.

    An unqualified SHA would imply the outputs are reproducible from that commit
    even when they were produced by modified code.
    """
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO, text=True
        ).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=REPO, text=True
        ).strip()
        return f"{sha}-dirty" if dirty else sha
    except Exception:
        return "unknown"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--allow-missing", action="store_true",
        help="write outputs even if a registered hazard layer is absent",
    )
    args = ap.parse_args()
    skipped: list[str] = []

    dc = pd.read_csv(DC_CSV, low_memory=False)
    lon = dc["longitude"].astype(float).to_numpy()
    lat = dc["latitude"].astype(float).to_numpy()
    n = len(dc)

    out = dc[[c for c in CARRY if c in dc.columns]].copy()
    cov: dict[str, dict] = {}
    print(f"Facilities: {n}\n")

    # --- Lightning -------------------------------------------------------------
    # NOTE: 0.5 degree (~50 km) climatology. This is a REGIONAL value attached to
    # a facility, not a building-scale measurement. Documented as such.
    if LIGHTNING_TIF.exists():
        v = sample_raster_at_points(LIGHTNING_TIF, lon, lat)
        out["haz_lightning_flash_per_km2_yr"] = v
        k = int(np.isfinite(v).sum())
        cov["lightning"] = {
            "column": "haz_lightning_flash_per_km2_yr",
            "measured": k, "imputed": 0, "total": n,
            "native_resolution": "0.5 deg (~50 km)",
            "distinct_values": int(pd.Series(v).nunique(dropna=True)),
            "units": "flashes/km2/yr",
        }
        print(f"  [ok]   lightning  measured {k}/{n}  "
              f"({cov['lightning']['distinct_values']} distinct values - regional scale)")
    else:
        skipped.append("lightning")
        print("  [skip] lightning  layer missing")

    # --- Seismic, all three return periods -------------------------------------
    for tag, rp in SEISMIC_LEVELS.items():
        shp = SEISMIC_DIR / f"US_PGA_{tag}50Yrs_BC_poly.shp"
        col = f"haz_seismic_pga_g_{rp}yr"
        if not shp.exists():
            skipped.append(f"seismic_{rp}yr")
            print(f"  [skip] seismic {rp}yr  layer missing")
            continue
        res = join_polygon_value(
            lon, lat, shp,
            value_fn=lambda g: (g["low_cont"].astype(float)
                                + g["high_cont"].astype(float)) / 2.0,
            nodata_mask_fn=lambda g: g["low_cont"].astype(float) <= -1e6,
            fill_nearest=False,          # no silent imputation
        )
        out[col] = res["value"]
        out[f"{col}_method"] = res["method"]
        meas = int((res["method"] == 1).sum())
        imp = int((res["method"] == 2).sum())
        cov[f"seismic_{rp}yr"] = {
            "column": col, "measured": meas, "imputed": imp, "total": n,
            "multi_polygon_matches": int(res["n_multi_match"]),
            "units": "g (PGA, site class BC / Vs30 760 m/s reference rock)",
            "note": "contour-band midpoint; band width 0.01 g so +/-0.005 g discretisation",
        }
        print(f"  [ok]   seismic {rp:4d}yr  measured {meas}/{n}  imputed {imp}")

    # --- Wildfire ---------------------------------------------------------------
    if WHP_TIF.exists():
        raw = sample_raster_at_points(WHP_TIF, lon, lat)
        out["haz_wildfire_whp_code"] = raw          # raw code incl. 6/7
        # Ordinal severity ONLY (1-5). 6/7 are nominal -> NaN here so that any
        # mean/rank/correlation on this column is arithmetically valid.
        sev = np.where(np.isin(raw, list(WHP_SEVERITY)), raw, np.nan)
        out["haz_wildfire_whp_severity"] = sev
        out["haz_wildfire_surface"] = pd.Series(raw).map(
            {**{k: v for k, v in WHP_SEVERITY.items()},
             WHP_NONBURNABLE: "non_burnable", WHP_WATER: "water"}
        ).to_numpy()

        # Structure risk in the WUI is driven by the SURROUNDINGS, not the pixel
        # under the slab. Buffer statistics are the defensible metric.
        for r in WHP_RADII_M:
            buf = sample_raster_in_buffer(WHP_TIF, lon, lat, radius_m=r)
            frac = np.full(n, np.nan)
            mx = np.full(n, np.nan)
            for i, vals in enumerate(buf["values"]):
                if vals.size == 0:
                    continue
                burnable = vals[(vals >= 1) & (vals <= 5)]
                frac[i] = burnable.size / vals.size
                # NaN, not 0: zero is not a WHP class. burnable_frac == 0
                # already records "no burnable land in radius".
                mx[i] = float(burnable.max()) if burnable.size else np.nan
            out[f"haz_wildfire_burnable_frac_{r}m"] = frac
            out[f"haz_wildfire_max_severity_{r}m"] = mx
            hi = int(np.nansum(mx >= 4))
            print(f"  [ok]   wildfire buffer {r:5d}m  facilities with High/VeryHigh nearby: {hi}")

        k_sev = int(np.isfinite(sev).sum())
        cov["wildfire"] = {
            "column_raw": "haz_wildfire_whp_code",
            "column_ordinal": "haz_wildfire_whp_severity",
            "measured_any_code": int(np.isfinite(raw).sum()),
            "measured_ordinal_1_5": k_sev,
            "non_burnable_code6": int((raw == WHP_NONBURNABLE).sum()),
            "water_code7": int((raw == WHP_WATER).sum()),
            "total": n,
            "native_resolution": "270 m (EPSG:5070)",
            "warning": "codes 6 and 7 are NOMINAL surface classes, not a continuation "
                       "of the 1-5 ordinal severity scale; never average the raw code",
            "buffer_radii_m": list(WHP_RADII_M),
        }
        print(f"  [ok]   wildfire   ordinal severity present for {k_sev}/{n} "
              f"(rest are developed/water surfaces)")
    else:
        skipped.append("wildfire")
        print("  [skip] wildfire  layer missing")

    # --- Authoritative seismic, replacing the contour-sampled 2475 yr value -----
    # Validation showed the contour product's magnitudes are unreliable (only
    # 22 of 150 within 10% of the USGS value, error spanning -54% to +130%).
    # The USGS ASCE 7-22 service returns the value for the exact coordinate.
    if SEISMIC_POINTS.exists():
        recs = {}
        with open(SEISMIC_POINTS) as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                if not r.get("error"):
                    recs[r["facility_id"]] = r
        fid = out["facility_id"].astype(str)
        out["haz_seismic_pga_g_2475yr_usgs"] = fid.map(
            lambda f: recs.get(f, {}).get("pgam"))
        # Spectral accelerations: Sa(1s) is the demand parameter that actually
        # distinguishes a tall building from a low one, unlike PGA.
        out["haz_seismic_sa_02s_g"] = fid.map(lambda f: recs.get(f, {}).get("ss"))
        out["haz_seismic_sa_1s_g"] = fid.map(lambda f: recs.get(f, {}).get("s1"))
        # ASCE 41-17 hazard levels. BSE-2E is 5% in 50 yr (about 975 yr) and
        # BSE-1E is 20% in 50 yr (about 225 yr). These are the only authoritative
        # values available below the 2,475 yr level from a public point service,
        # and they are spectral accelerations rather than PGA.
        for lvl, rp in (("bse_2e", 975), ("bse_1e", 225)):
            out[f"haz_seismic_sa_02s_g_{rp}yr"] = fid.map(
                lambda f, lv=lvl: recs.get(f, {}).get(f"{lv}_ss"))
            out[f"haz_seismic_sa_1s_g_{rp}yr"] = fid.map(
                lambda f, lv=lvl: recs.get(f, {}).get(f"{lv}_s1"))
        out["haz_seismic_source"] = np.where(
            out["haz_seismic_pga_g_2475yr_usgs"].notna(),
            "USGS ASCE 7-22 point service (site class BC)", "contour sample")
        k = int(out["haz_seismic_pga_g_2475yr_usgs"].notna().sum())
        cov["seismic_authoritative"] = {
            "column": "haz_seismic_pga_g_2475yr_usgs",
            "measured": k, "total": n,
            "source": "USGS ASCE 7-22 web service, siteClass=BC (Vs30 760 m/s)",
            "asce41_levels": {
                "bse_2e": "5% in 50 yr (~975 yr), spectral acceleration only",
                "bse_1e": "20% in 50 yr (~225 yr), spectral acceleration only"},
            "note": "Authoritative PGA is available only at the 2% in 50 yr "
                    "(~2475 yr) level. No public point service returns PGA at "
                    "475 or 975 yr, so those two columns remain contour-derived "
                    "and are APPROXIMATE: across all 2,696 facilities the "
                    "contour method agreed with the authoritative value within "
                    "10% for only 425 (16%). ASCE 41 spectral accelerations at "
                    "~975 yr and ~225 yr are provided as the authoritative "
                    "multi-level alternative.",
        }
        print(f"  [ok]   seismic USGS point service  measured {k}/{n} "
              f"(replaces contour magnitudes at 2475 yr)")

    # --- NSHM hazard curves, replacing the contour-sampled 475 and 975 yr -------
    # The ASCE 7-22 service above reports one hazard level, so 475 and 975 yr
    # stayed contour-derived and approximate. These come off the NSHM's own PGA
    # hazard curve at each facility, interpolated to 1/475 and 1/975 annual
    # exceedance. All three NSHM levels come from one curve, so unlike the
    # previous mix they are internally consistent with each other.
    if SEISMIC_NSHM.exists():
        lv: dict[str, dict] = {}
        with open(SEISMIC_NSHM) as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                if not r.get("error"):
                    lv[str(r["facility_id"])] = r      # last good row wins
        fid = out["facility_id"].astype(str)
        for rp in (475, 975, 2475):
            out[f"haz_seismic_pga_g_{rp}yr_nshm"] = fid.map(
                lambda f, p=rp: lv.get(f, {}).get(f"pga_g_{p}yr"))
        k475 = int(out["haz_seismic_pga_g_475yr_nshm"].notna().sum())
        k975 = int(out["haz_seismic_pga_g_975yr_nshm"].notna().sum())

        # Agreement between the NSHM's own 2,475 yr level and the ASCE 7-22
        # value. These are not required to match: ASCE 7-22 is a design-code
        # product built on an earlier model revision. Recording the spread makes
        # the vintage difference measurable instead of hidden.
        cmp_note = None
        if "haz_seismic_pga_g_2475yr_usgs" in out:
            a = pd.to_numeric(out["haz_seismic_pga_g_2475yr_usgs"], errors="coerce")
            b = pd.to_numeric(out["haz_seismic_pga_g_2475yr_nshm"], errors="coerce")
            both = a.notna() & b.notna() & (a > 0)
            if int(both.sum()):
                rel = ((b[both] - a[both]) / a[both] * 100)
                cmp_note = {
                    "n_compared": int(both.sum()),
                    "median_rel_diff_pct": round(float(rel.median()), 2),
                    "within_10pct": int((rel.abs() <= 10).sum()),
                    "within_25pct": int((rel.abs() <= 25).sum()),
                }
        cov["seismic_nshm"] = {
            "columns": [f"haz_seismic_pga_g_{rp}yr_nshm" for rp in (475, 975, 2475)],
            "measured_475": k475, "measured_975": k975, "total": n,
            "source": "USGS NSHM conus-2023.R2 static hazard curves, "
                      "NEHRP site class BC, log-log interpolated to 1/N",
            "supersedes": ["haz_seismic_pga_g_475yr", "haz_seismic_pga_g_975yr"],
            "nshm_vs_asce7_at_2475yr": cmp_note,
            "note": "The plain haz_seismic_pga_g_475yr / _975yr columns are the "
                    "old contour samples and are kept only for comparison. Use "
                    "the _nshm columns. A null means the return period fell "
                    "outside the tabulated curve at that site, which is not the "
                    "same as zero hazard.",
        }
        print(f"  [ok]   seismic NSHM curves  475yr {k475}/{n}, 975yr {k975}/{n}"
              + (f"  |  vs ASCE 7-22 at 2475yr: median "
                 f"{cmp_note['median_rel_diff_pct']:+.1f}%, "
                 f"{cmp_note['within_25pct']}/{cmp_note['n_compared']} within 25%"
                 if cmp_note else ""))
    else:
        skipped.append("seismic_nshm")
        print("  [skip] seismic NSHM  cache missing, run fetch_seismic_nshm.py")

    # --- QA flag: coordinates that landed on water ------------------------------
    if "haz_wildfire_whp_code" in out:
        on_water = out["haz_wildfire_whp_code"] == WHP_WATER
        out["qa_coordinate_on_water"] = on_water
        if int(on_water.sum()):
            print(f"\n  [qa]   {int(on_water.sum())} facilities sample on an open-water "
                  f"pixel - coordinate error, flagged not dropped")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)

    meta = {
        "generated": date.today().isoformat(),
        "git_commit": _git_sha(),
        "n_facilities": n,
        "source_table": str(DC_CSV.relative_to(REPO)),
        "hazards": cov,
        "skipped_layers": skipped,
        "caveats": [
            "Values are sampled at a single facility point, not intersected with "
            "the building footprint. Adequate where the hazard's correlation "
            "length greatly exceeds the building (seismic, lightning); a known "
            "limitation for wildfire (270 m) and for flood once added.",
            "Seismic values are reference-rock (site class BC, Vs30 760 m/s) and "
            "are therefore a systematic underestimate at soft-soil sites.",
            "Exposure only. No vulnerability or consequence term is applied, so "
            "these columns are not risk estimates.",
        ],
    }
    OUT_JSON.write_text(json.dumps(meta, indent=2) + "\n")
    print(f"\nWrote {OUT_CSV.relative_to(REPO)}  ({len(out)} rows, {len(out.columns)} cols)")
    print(f"Wrote {OUT_JSON.relative_to(REPO)}")

    if skipped:
        msg = ("missing hazard layers: " + ", ".join(skipped)
               + "\nRun scripts/fetch_hazard_data.py, or pass --allow-missing "
                 "to accept a partial table.")
        if not args.allow_missing:
            raise SystemExit(f"ERROR: {msg}")
        print(f"\nWARNING: {msg}")


if __name__ == "__main__":
    main()
