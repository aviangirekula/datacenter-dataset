"""Publication figures for paper/manuscript.md.

Deliberately different from the poster figures. The poster is read at three feet
and carries three large graphics; these are read at arm's length in a column and
carry the caveats the text argues for.

Five figures, each answering one question the manuscript raises:

  fig1_map          where the facilities are, and how they qualified
  fig2_states       the full 32-state distribution, not a selection
  fig3_sensitivity  what the two unjustified thresholds are worth
  fig4_overlap      how little hazard and water stress share
  fig5_seismic      the three-product disagreement

Design rules applied: categorical hues assigned in fixed order and never cycled,
one axis per panel, no dual axes, thin marks, recessive grid, a legend whenever
more than one series is drawn. The palette is Okabe-Ito and was checked with a
colour-vision validator: the four categorical hues pass lightness, chroma, CVD
separation and normal-vision separation. Orange falls below 3:1 contrast against
white, which is why every figure that uses it also carries a legend and direct
labels rather than relying on hue alone. Grey is a deliberate baseline neutral for
"no criterion met", not a categorical series.

    ./.venv/bin/python scripts/make_paper_figures.py
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

REPO = Path(__file__).resolve().parents[1]
P = REPO / "data" / "processed"
OUT = REPO / "figures" / "paper"
DPI = 300

# Okabe-Ito. Fixed order, never cycled.
ORANGE = "#E69F00"      # wildfire proximity
BLUE = "#0072B2"        # containment (flood or earthquake)
VERM = "#D55E00"
TEAL = "#009E73"
NEUTRAL = "#9E9E9E"     # baseline: no criterion met
INK, INK2, INK3 = "#1a1a1a", "#4a4a4a", "#767676"
GRID = "#e0e0e0"

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 8,
    "axes.labelsize": 8,
    "axes.titlesize": 8.5,
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5,
    "legend.fontsize": 7.5,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "axes.edgecolor": INK3,
    "axes.linewidth": 0.6,
    "xtick.color": INK2, "ytick.color": INK2,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6,
})


def load() -> pd.DataFrame:
    h = pd.read_csv(P / "hazard_exposure.csv", low_memory=False)
    b = pd.read_csv(P / "building_attributes.csv", low_memory=False)
    w = pd.read_csv(P / "water_stress.csv")
    d = h.merge(b[["facility_id", "flood_sfha"]], on="facility_id", how="left")
    d = d.merge(w[["facility_id", "water_stress_class"]], on="facility_id",
                how="left")
    d["f_fire"] = (d["haz_wildfire_max_severity_2400m"] >= 4).fillna(False)
    d["f_flood"] = (d["flood_sfha"] == True)          # noqa: E712 - NaN is not True
    d["f_quake"] = (d["haz_seismic_pga_g_2475yr_usgs"] >= 0.3).fillna(False)
    d["n_haz"] = d[["f_fire", "f_flood", "f_quake"]].sum(axis=1)
    # The manuscript's central distinction: containment versus proximity.
    d["contain"] = d["f_flood"] | d["f_quake"]
    d["prox_only"] = d["f_fire"] & ~d["contain"]
    d["water"] = d["water_stress_class"].isin(["high", "extremely_high"])
    return d


def states_5070():
    shp = REPO / "data" / "raw" / "tiger" / "tl_2024_us_county.shp"
    if not shp.exists():
        return None
    g = gpd.read_file(shp, columns=["STATEFP", "geometry"])
    g = g[~g["STATEFP"].isin({"02", "15", "60", "66", "69", "72", "78"})]
    return g.dissolve(by="STATEFP").to_crs("EPSG:5070")


def save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"{name}.{ext}", dpi=DPI, bbox_inches="tight",
                    pad_inches=0.02)
    plt.close(fig)
    print(f"  {name}")


# --- Fig 1: national map -------------------------------------------------------

def fig_map(d: pd.DataFrame) -> None:
    """Facilities by how they qualified, not merely whether they did.

    Three classes rather than a hazard count, because the manuscript's point is
    that most exposed facilities qualified on proximity and would not qualify on
    containment.
    """
    base = states_5070()
    pts = gpd.GeoDataFrame(
        d, geometry=gpd.points_from_xy(d["longitude"], d["latitude"]),
        crs="EPSG:4326").to_crs("EPSG:5070")

    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    if base is not None:
        base.plot(ax=ax, facecolor="#f7f7f7", edgecolor="white", linewidth=0.5,
                  zorder=1)

    spec = [
        (pts[~pts["contain"] & ~pts["prox_only"]], NEUTRAL, 3.0,
         "No criterion met"),
        (pts[pts["prox_only"]], ORANGE, 5.0,
         "Wildfire proximity only"),
        (pts[pts["contain"]], BLUE, 6.0,
         "Flood or earthquake (containment)"),
    ]
    for sel, colour, size, _ in spec:
        sel.plot(ax=ax, color=colour, markersize=size, linewidth=0, zorder=2)

    handles = [Line2D([0], [0], marker="o", linestyle="none",
                      markerfacecolor=c, markeredgecolor="none",
                      markersize=np.sqrt(s) * 1.6, label=f"{lab}  (n={len(sel):,})")
               for sel, c, s, lab in spec]
    leg = ax.legend(handles=handles, loc="lower center", ncol=3, frameon=False,
                    bbox_to_anchor=(0.5, -0.06), handletextpad=0.5,
                    columnspacing=1.6)
    for t in leg.get_texts():
        t.set_color(INK2)
    ax.set_axis_off()
    fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.06)
    save(fig, "fig1_map")


# --- Fig 2: all 32 states ------------------------------------------------------

def fig_states(d: pd.DataFrame) -> None:
    """Every state with 20 or more facilities, not a selection.

    Showing a subset is what produced a retracted claim earlier in this project,
    so the full set is plotted and the band-sensitivity is drawn rather than
    described.
    """
    g = (d.groupby("state")
           .agg(n=("facility_id", "size"),
                pct=("n_haz", lambda s: 100 * (s >= 1).mean()))
           .query("n >= 20").sort_values("pct"))
    y = np.arange(len(g))

    fig, ax = plt.subplots(figsize=(3.6, 6.0))
    ax.axvspan(10, 60, color="#f2f2f2", zorder=0, lw=0)
    ax.axvspan(5, 95, facecolor="none", edgecolor=INK3, lw=0.5, ls=(0, (3, 3)),
               zorder=1)

    # One series, one colour. Colouring the marks by which band they fall in
    # would encode rank rather than identity, and would reuse hues that carry a
    # different meaning in Figure 1. The bands are drawn, so the reader can see
    # the grouping without the marks asserting it.
    ax.hlines(y, 0, g["pct"], color=BLUE, lw=1.3, zorder=3, alpha=0.85)
    ax.scatter(g["pct"], y, s=16, c=BLUE, zorder=4, linewidths=0)

    ax.set_yticks(y)
    ax.set_yticklabels([f"{s}  ({n:,})" for s, n in zip(g.index, g["n"])],
                       fontsize=7)
    ax.set_xlim(-2, 104)
    ax.set_ylim(-1, len(g))
    ax.set_xlabel("Facilities meeting at least one criterion (%)")
    ax.xaxis.grid(True, color=GRID, lw=0.5, zorder=0)
    ax.set_axisbelow(True)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)

    mid = ((g["pct"] >= 10) & (g["pct"] <= 60)).sum()
    wide = ((g["pct"] >= 5) & (g["pct"] <= 95)).sum()
    ax.set_title(f"{len(g)} states with 20+ facilities.\n"
                 f"Shaded 10-60% band holds {mid}; dashed 5-95% band holds {wide}.",
                 loc="left", color=INK, pad=8, linespacing=1.4)
    save(fig, "fig2_states")


# --- Fig 3: threshold sensitivity ---------------------------------------------

def fig_sensitivity(d: pd.DataFrame) -> None:
    """What the two unjustified choices are worth.

    Neither the 2.4 km buffer nor the 0.30 g cut is anchored to a published
    boundary, so both are drawn as curves and the operating point is marked.
    Two panels, one axis each, never a shared twin axis.
    """
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.6))

    # (a) wildfire buffer radius
    radii = [1000, 2400, 5000]
    counts = [int((d[f"haz_wildfire_max_severity_{r}m"] >= 4).sum()) for r in radii]
    ax = axes[0]
    ax.plot([r / 1000 for r in radii], counts, color=ORANGE, lw=1.6,
            marker="o", ms=5, zorder=3)
    for r, c in zip(radii, counts):
        ax.annotate(f"{c:,}", (r / 1000, c), xytext=(0, 7),
                    textcoords="offset points", ha="center", fontsize=7.5,
                    color=INK)
    ax.axvline(2.4, color=INK3, lw=0.7, ls=(0, (3, 3)), zorder=2)
    ax.set_xlabel("Wildfire buffer radius (km)")
    ax.set_ylabel("Facilities flagged")
    ax.set_title("(a) Wildfire proximity criterion", loc="left", color=INK)

    # (b) seismic threshold
    pga = pd.to_numeric(d["haz_seismic_pga_g_2475yr_usgs"], errors="coerce")
    thr = np.arange(0.10, 1.005, 0.01)
    quake = [int((pga >= t).sum()) for t in thr]
    total = [int((d["f_fire"] | d["f_flood"] | (pga >= t)).sum()) for t in thr]
    ax = axes[1]
    ax.plot(thr, total, color=BLUE, lw=1.6, zorder=3,
            label="Any criterion met")
    ax.plot(thr, quake, color=TEAL, lw=1.6, zorder=3,
            label="Earthquake criterion")
    ax.axvline(0.30, color=INK3, lw=0.7, ls=(0, (3, 3)), zorder=2)
    i = int(np.argmin(np.abs(thr - 0.30)))
    ax.scatter([0.30, 0.30], [total[i], quake[i]], s=18,
               c=[BLUE, TEAL], zorder=4, linewidths=0)
    ax.annotate(f"{total[i]:,}", (0.30, total[i]), xytext=(6, 3),
                textcoords="offset points", fontsize=7.5, color=INK)
    ax.annotate(f"{quake[i]:,}", (0.30, quake[i]), xytext=(6, 3),
                textcoords="offset points", fontsize=7.5, color=INK)
    ax.set_xlabel("Seismic threshold (g)")
    ax.set_title("(b) Earthquake criterion", loc="left", color=INK)
    leg = ax.legend(frameon=False, loc="upper right")
    for t in leg.get_texts():
        t.set_color(INK2)

    # Both panels count the same thing, so they share a scale. Letting each pick
    # its own would make a 646 look like a 954.
    top = max(max(counts), max(total)) * 1.15
    axes[1].set_ylabel("")
    axes[1].tick_params(labelleft=False)
    for ax in axes:
        ax.set_ylim(0, top)
        ax.yaxis.grid(True, color=GRID, lw=0.5)
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    axes[0].annotate("reported", (2.4, top * 0.03), xytext=(4, 0),
                     textcoords="offset points", fontsize=7, color=INK3)
    axes[1].annotate("reported", (0.30, top * 0.03), xytext=(4, 0),
                     textcoords="offset points", fontsize=7, color=INK3)
    fig.subplots_adjust(wspace=0.32)
    save(fig, "fig3_sensitivity")


# --- Fig 4: hazard versus water stress ----------------------------------------

def fig_overlap(d: pd.DataFrame) -> None:
    """Set composition, drawn as one stacked bar rather than a Venn diagram.

    A proportional Venn cannot be drawn accurately for these three quantities in
    two dimensions, and an inaccurate one would misstate the very overlap the
    figure exists to show.
    """
    haz = d["n_haz"] >= 1
    wat = d["water"]
    parts = [
        ("Hazard criterion only", int((haz & ~wat).sum()), BLUE),
        ("Both", int((haz & wat).sum()), VERM),
        ("Water stress only", int((~haz & wat).sum()), TEAL),
        ("Neither", int((~haz & ~wat).sum()), NEUTRAL),
    ]
    total = sum(v for _, v, _ in parts)

    fig, ax = plt.subplots(figsize=(7.0, 1.15))
    left = 0.0
    for lab, v, c in parts:
        ax.barh(0, v, left=left, color=c, height=0.5, zorder=3,
                edgecolor="white", linewidth=1.2)
        ax.annotate(f"{v:,}\n{100*v/total:.1f}%", (left + v / 2, 0),
                    ha="center", va="center", fontsize=7.5, color="white"
                    if c != NEUTRAL else INK, fontweight="bold",
                    linespacing=1.25, zorder=4)
        left += v

    handles = [mpl.patches.Patch(facecolor=c, edgecolor="none", label=lab)
               for lab, _, c in parts]
    leg = ax.legend(handles=handles, loc="upper center", ncol=4, frameon=False,
                    bbox_to_anchor=(0.5, -0.02), handlelength=1.1,
                    handletextpad=0.5, columnspacing=1.6)
    for t in leg.get_texts():
        t.set_color(INK2)
    ax.set_xlim(0, total)
    ax.set_ylim(-0.30, 0.30)
    ax.set_yticks([])
    ax.set_xticks([])
    ax.set_title(f"All {total:,} facilities. Hazard criteria and water stress "
                 f"select {parts[0][1]:,} and {parts[2][1]:,} disjoint "
                 f"facilities against {parts[1][1]:,} shared.",
                 loc="left", color=INK, pad=6)
    for sp in ax.spines.values():
        sp.set_visible(False)
    save(fig, "fig4_overlap")


# --- Fig 5: seismic product comparison ----------------------------------------

def fig_seismic(d: pd.DataFrame) -> None:
    """Why the earthquake count is uncertain by 139 facilities.

    Plotted against the 1:1 line so the offset is read as a displacement rather
    than inferred from two summary statistics.
    """
    a = pd.to_numeric(d["haz_seismic_pga_g_2475yr_usgs"], errors="coerce")
    n = pd.to_numeric(d["haz_seismic_pga_g_2475yr_nshm"], errors="coerce")
    c = pd.to_numeric(d["haz_seismic_pga_g_2475yr"], errors="coerce")
    m = a.notna() & n.notna() & c.notna() & (a > 0) & (n > 0) & (c > 0)

    fig, ax = plt.subplots(figsize=(3.6, 3.4))
    lim = [min(a[m].min(), n[m].min()) * 0.8, max(a[m].max(), n[m].max()) * 1.2]
    ax.plot(lim, lim, color=INK3, lw=0.8, ls=(0, (3, 3)), zorder=2,
            label="1:1")
    ax.scatter(a[m], n[m], s=4, c=BLUE, alpha=0.35, linewidths=0, zorder=3,
               label="NSHM hazard curves")
    ax.scatter(a[m], c[m], s=4, c=ORANGE, alpha=0.35, linewidths=0, zorder=3,
               label="NSHM contour maps")
    ax.axvline(0.30, color=INK3, lw=0.6, zorder=1)
    ax.axhline(0.30, color=INK3, lw=0.6, zorder=1)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_xlabel("ASCE 7-22 service, PGA (g)")
    ax.set_ylabel("NSHM 2023 product, PGA (g)")
    med = float(((n[m] - a[m]) / a[m] * 100).median())
    ax.set_title(f"Both NSHM products sit above the design-code service\n"
                 f"(median +{med:.0f}%). Lines mark the 0.30 g criterion.",
                 loc="left", color=INK, pad=8, linespacing=1.4)
    leg = ax.legend(frameon=False, loc="upper left", markerscale=2.2)
    for t in leg.get_texts():
        t.set_color(INK2)
    ax.grid(True, which="major", color=GRID, lw=0.5)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    save(fig, "fig5_seismic")


def main() -> None:
    d = load()
    print(f"facilities {len(d):,} | any criterion "
          f"{int((d['n_haz'] >= 1).sum()):,} | proximity-only "
          f"{int(d['prox_only'].sum()):,} | containment "
          f"{int(d['contain'].sum()):,}")
    fig_map(d)
    fig_states(d)
    fig_sensitivity(d)
    fig_overlap(d)
    fig_seismic(d)
    print(f"\nWrote to {OUT.relative_to(REPO)} (png + pdf, {DPI} dpi)")


if __name__ == "__main__":
    main()
