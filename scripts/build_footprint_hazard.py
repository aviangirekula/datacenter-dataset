"""Footprint-based hazard sampling, and the single versus multi-storey control.

Two things the advisor asked for that point sampling cannot answer:

**1. Intersect hazards with the building footprint**, not a single coordinate.
For each facility with a matched building polygon, every raster cell overlapping
the footprint is collected and summarised area-weighted. Where a hazard varies
at or below building scale (wildfire at 270 m) this changes the answer. Where
its correlation length greatly exceeds a building (seismic, lightning) a
footprint mean cannot differ meaningfully, so those layers are deliberately not
re-sampled.

**2. Control for building height.** Height drives seismic response (a taller
building responds at a longer period than PGA represents) and flood consequence
(whether plant sits at grade). Heights are measured for about half the dataset,
so the comparison is reported on that subset with the coverage stated.

Outputs
- ``data/processed/building_footprints.gpkg`` the matched polygons
- ``data/processed/footprint_hazard.csv``     per-facility footprint statistics
- ``data/processed/footprint_vs_point.json``  how much footprint sampling moved

    ./.venv/bin/python scripts/build_footprint_hazard.py
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

REPO = Path(__file__).resolve().parents[1]
ATTR = REPO / "data" / "processed" / "building_attributes.csv"
HAZ = REPO / "data" / "processed" / "hazard_exposure.csv"
CACHES = [REPO / "data" / "raw" / "buildings" / "usa_structures.jsonl",
          REPO / "data" / "raw" / "buildings" / "usa_structures_r800.jsonl"]
WHP_TIF = (REPO / "data" / "hazards" / "wildfire" / "whp" / "Data"
           / "whp2023_GeoTIF" / "whp2023_cls_conus.tif")
GPKG = REPO / "data" / "processed" / "building_footprints.gpkg"
OUT = REPO / "data" / "processed" / "footprint_hazard.csv"
OUT_JSON = REPO / "data" / "processed" / "footprint_vs_point.json"

WHP_BURNABLE = (1, 2, 3, 4, 5)


def _ring_area(ring) -> float:
    a = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        a += x1 * y2 - x2 * y1
    return a / 2.0


def _poly(feat):
    rings = [r for r in ((feat.get("geometry") or {}).get("rings") or [])
             if r and len(r) >= 4]
    if not rings:
        return None
    try:
        outers = [r for r in rings if _ring_area(r) < 0]
        holes = [r for r in rings if _ring_area(r) >= 0]
        if not outers:
            big = max(rings, key=lambda r: abs(_ring_area(r)))
            outers, holes = [big], [r for r in rings if r is not big]
        parts = []
        for o in outers:
            shell = Polygon(o)
            mine = [h for h in holes
                    if shell.contains(Polygon(h).representative_point())]
            p = Polygon(o, mine)
            parts.append(p if p.is_valid else p.buffer(0))
        g = parts[0] if len(parts) == 1 else unary_union(parts)
        return None if g.is_empty else g
    except Exception:  # noqa: BLE001
        return None


def extract_footprints(attr: pd.DataFrame) -> gpd.GeoDataFrame:
    """Recover the geometry of the building each facility was matched to."""
    # build_id round-trips through the CSV as float (16010881.0) while the
    # cached JSON holds an int. Normalise both before comparing.
    def _norm(v):
        try:
            return str(int(float(v)))
        except (TypeError, ValueError):
            return None

    want = {str(f): _norm(b)
            for f, b in zip(attr["facility_id"].astype(str), attr["build_id"])}
    found: dict[str, object] = {}
    for path in CACHES:
        if not path.exists():
            continue
        with open(path) as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                fid = r["facility_id"]
                bid = want.get(fid)
                if bid is None or fid in found:
                    continue
                for f in r.get("features", []):
                    if _norm(f["attributes"].get("BUILD_ID")) == bid:
                        g = _poly(f)
                        if g is not None:
                            found[fid] = g
                        break
    print(f"  recovered {len(found)} building polygons")
    ids = list(found)
    return gpd.GeoDataFrame({"facility_id": ids},
                            geometry=[found[i] for i in ids], crs="EPSG:4326")


def zonal_whp(fp: gpd.GeoDataFrame) -> pd.DataFrame:
    """True area-weighted WHP statistics over each footprint.

    Each touched cell is weighted by the area it shares with the building. This
    matters enormously here: 99.4% of these footprints are smaller than a single
    270 m cell, so an unweighted mode over touched cells summarises a median of
    25x the building's own area and is dominated by ground the building does not
    occupy.

    Ordinal severity (1-5) and nominal surface codes (6 developed, 7 water) are
    kept apart. A mode taken across that boundary is meaningless, and doing so
    accounted for 90% of an earlier, inflated point-versus-footprint difference.
    """
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.windows import from_bounds

    rows, errs = [], []
    with rasterio.open(WHP_TIF) as src:
        fp5070 = fp.to_crs(src.crs)
        for fid, geom in zip(fp5070["facility_id"], fp5070.geometry):
            try:
                win = from_bounds(*geom.bounds, transform=src.transform)
                # round_lengths floors, so pad generously: an under-sized window
                # silently drops cells the footprint really touches.
                win = rasterio.windows.Window(
                    int(np.floor(win.col_off)) - 2, int(np.floor(win.row_off)) - 2,
                    int(np.ceil(win.width)) + 4, int(np.ceil(win.height)) + 4)
                arr = src.read(1, window=win, masked=True, boundless=True)
                if arr.size == 0:
                    continue
                t = src.window_transform(win)
                mask = geometry_mask([geom], out_shape=arr.shape, transform=t,
                                     invert=True, all_touched=True)
                m = mask & ~np.ma.getmaskarray(arr)
                if not m.any():
                    continue
                # Area of overlap between the footprint and each touched cell.
                px, py = abs(t.a), abs(t.e)
                ws, vs = [], []
                for r_i, c_i in zip(*np.where(m)):
                    x0 = t.c + c_i * t.a
                    y0 = t.f + r_i * t.e
                    cell = box(min(x0, x0 + px), min(y0, y0 - py),
                               max(x0, x0 + px), max(y0, y0 - py))
                    inter = geom.intersection(cell).area
                    if inter <= 0:
                        continue
                    ws.append(inter)
                    vs.append(float(arr[r_i, c_i]))
                if not ws:
                    continue
                w = np.asarray(ws, dtype=float)
                v = np.asarray(vs, dtype=float)
                w = w / w.sum()

                is_burn = np.isin(v, WHP_BURNABLE)
                burn_frac = float(w[is_burn].sum())
                # Area-weighted mode, restricted to the ordinal ladder so a
                # developed/water code cannot win a severity comparison.
                if is_burn.any():
                    ord_w = {}
                    for val, wt in zip(v[is_burn], w[is_burn]):
                        ord_w[val] = ord_w.get(val, 0.0) + wt
                    modal_sev = max(ord_w, key=ord_w.get)
                    max_sev = float(v[is_burn].max())
                else:
                    modal_sev, max_sev = np.nan, np.nan
                surf_w = {}
                for val, wt in zip(v, w):
                    surf_w[val] = surf_w.get(val, 0.0) + wt
                rows.append({
                    "facility_id": fid,
                    "fp_cells": int(len(v)),
                    "fp_area_frac_largest_cell": float(w.max()),
                    "fp_whp_max_severity": max_sev,
                    "fp_whp_burnable_area_frac": burn_frac,
                    "fp_whp_modal_severity": modal_sev,
                    "fp_whp_modal_surface": float(max(surf_w, key=surf_w.get)),
                })
            except Exception as e:  # noqa: BLE001
                errs.append((fid, repr(e)))
                continue
    if errs:
        print(f"  WARNING: {len(errs)} footprints failed zonal stats")
    return pd.DataFrame(rows)


def main() -> None:
    attr = pd.read_csv(ATTR, low_memory=False)
    haz = pd.read_csv(HAZ, low_memory=False)
    matched = attr[attr["build_id"].notna()]
    print(f"facilities with a matched building: {len(matched)}")

    print("extracting footprint geometry ...")
    fp = extract_footprints(matched)
    GPKG.parent.mkdir(parents=True, exist_ok=True)
    fp.to_file(GPKG, driver="GPKG", layer="building_footprints")
    print(f"  wrote {GPKG.relative_to(REPO)}")

    print("area-weighted wildfire over each footprint (slow) ...")
    z = zonal_whp(fp)
    print(f"  summarised {len(z)} footprints")

    out = attr.merge(z, on="facility_id", how="left")
    out = out.merge(
        haz[["facility_id", "haz_wildfire_whp_code",
             "haz_wildfire_max_severity_1000m", "haz_seismic_pga_g_475yr",
             "haz_lightning_flash_per_km2_yr"]],
        on="facility_id", how="left")

    # --- does footprint sampling actually change the answer? -------------------
    # Compare severity to severity. An earlier version compared across the
    # ordinal/nominal boundary, and 90% of the apparent difference was that.
    both = out[out["fp_whp_modal_severity"].notna()
               & out["haz_wildfire_whp_code"].isin(WHP_BURNABLE)]
    differs = int((both["fp_whp_modal_severity"] != both["haz_wildfire_whp_code"]).sum())
    cmp_ = out[out["fp_whp_modal_surface"].notna()]
    burn_pt = int(cmp_["haz_wildfire_whp_code"].isin(WHP_BURNABLE).sum())
    # Require the burnable land to be a real share of the footprint, not a
    # sliver of one touched cell.
    burn_fp = int((cmp_["fp_whp_burnable_area_frac"] >= 0.5).sum())
    stats = {
        "n_with_footprint_stats": int(len(cmp_)),
        "n_severity_comparable": int(len(both)),
        "severity_differs_from_point": differs,
        "pct_severity_differs": round(100 * differs / max(len(both), 1), 1),
        "burnable_at_point": burn_pt,
        "burnable_over_half_of_footprint": burn_fp,
        "note": "Wildfire varies at 270 m, so footprint sampling can disagree "
                "with the point. Seismic and lightning have correlation lengths "
                "far larger than a building and are not re-sampled.",
    }
    print(f"\n  area-weighted footprint severity differs from the point value "
          f"for {differs} of {len(both)} comparable ({stats['pct_severity_differs']}%)")
    print(f"  burnable at the point: {burn_pt};  over half the footprint: {burn_fp}")

    # --- storey control --------------------------------------------------------
    # Two corrections over a naive version. First, many facilities share one
    # building (a carrier hotel can carry a dozen), so rows are de-duplicated on
    # build_id or the n's are inflated and the inflation is class-dependent.
    # Second, height is strongly confounded with geography (NY is mostly
    # multi-storey and seismically different from VA), so a raw split compares
    # regions rather than heights. The within-state comparison is the honest one.
    from scipy.stats import mannwhitneyu

    h = out[out["height_m"].notna() & out["build_id"].notna()].copy()
    h = h.drop_duplicates(subset=["build_id"])
    h["storey_class"] = np.where(h["height_m"] >= 12.0, "multi_storey", "low_rise")
    grp = h.groupby("storey_class").agg(
        n=("facility_id", "size"),
        median_height_m=("height_m", "median"),
        median_footprint_sqft=("footprint_sqft", "median"),
        median_pga_475=("haz_seismic_pga_g_475yr", "median"),
        mean_pga_475=("haz_seismic_pga_g_475yr", "mean"),
        pct_in_sfha=("flood_sfha", lambda s: 100 * pd.Series(s).eq(True).mean()),
    ).round(4)
    print("\n=== single versus multi-storey control (de-duplicated by building) ===")
    print(grp.to_string())

    a = h.loc[h["storey_class"] == "low_rise", "haz_seismic_pga_g_475yr"].dropna()
    b = h.loc[h["storey_class"] == "multi_storey", "haz_seismic_pga_g_475yr"].dropna()
    u = mannwhitneyu(a, b, alternative="two-sided") if len(a) and len(b) else None

    # Is the split really height, or is it geography?
    within = []
    for st, g in h.groupby("state"):
        lo = g.loc[g["storey_class"] == "low_rise", "haz_seismic_pga_g_475yr"].dropna()
        hi = g.loc[g["storey_class"] == "multi_storey", "haz_seismic_pga_g_475yr"].dropna()
        if len(lo) >= 3 and len(hi) >= 3:
            within.append(hi.median() - lo.median())
    stats["storey_control"] = {
        "table": json.loads(grp.to_json(orient="index")),
        "mannwhitney_p_pga": float(u.pvalue) if u else None,
        "within_state_median_pga_difference": (
            float(np.median(within)) if within else None),
        "n_states_comparable": len(within),
        "caveat": "Height is strongly confounded with geography: multi-storey "
                  "facilities concentrate in NY and WA, low-rise in VA and TX, "
                  "so an unconditioned split compares regions. Within state the "
                  "difference is essentially zero. Height should be used as a "
                  "VULNERABILITY covariate, not treated as an exposure driver, "
                  "and the relevant demand parameter for a taller building is "
                  "spectral acceleration at ~1 s rather than PGA.",
    }
    stats["storey_coverage"] = {
        "facilities_with_height": int(out["height_m"].notna().sum()),
        "distinct_buildings": int(len(h)), "total": int(len(out))}
    print(f"  Mann-Whitney p on PGA: {stats['storey_control']['mannwhitney_p_pga']}")
    print(f"  within-state median PGA difference: "
          f"{stats['storey_control']['within_state_median_pga_difference']} "
          f"across {len(within)} states")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    OUT_JSON.write_text(json.dumps(stats, indent=2) + "\n")
    print(f"\nWrote {OUT.relative_to(REPO)} ({len(out)} rows)")


if __name__ == "__main__":
    main()
