"""Slide figure: wildfire exposure of US data centers.

Two panels. Left is a CONUS map with each facility shaded by how close it sits to
land rated High or Very High wildfire hazard (USFS WHP class >= 4). Right is the
count at each search radius. The tiers are nested, so the bars are cumulative.

    ./.venv/bin/python scripts/make_wildfire_figure.py
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D

REPO = Path(__file__).resolve().parents[1]
HAZ = REPO / "data" / "processed" / "hazard_exposure.csv"
STATES = REPO / "data" / "raw" / "tiger" / "cb_2020_us_state_20m.zip"
OUT = REPO / "figures" / "wildfire_exposure.png"

SURFACE = "#fcfcfb"
INK, INK2, INK3 = "#1a1a1a", "#4a4a4a", "#6e6e6e"
# Sequential ramp, light -> dark (validated monotonic), plus a neutral for absence.
NONE_C = "#D9D9D9"
RAMP = ["#FDD0A2", "#FD8D3C", "#D94801"]
LABELS = ["None within 5 km", "2.4 to 5 km", "1 to 2.4 km", "Within 1 km"]

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
})


def _basemap():
    """CONUS state outlines, dissolved from the cached TIGER county file."""
    county = REPO / "data" / "raw" / "tiger" / "tl_2024_us_county.shp"
    if not county.exists():
        return None
    g = gpd.read_file(county, columns=["STATEFP", "geometry"])
    # Drop AK, HI and the territories so the CONUS frame is not distorted.
    drop = {"02", "15", "60", "66", "69", "72", "78"}
    g = g[~g["STATEFP"].isin(drop)]
    return g.dissolve(by="STATEFP").to_crs("EPSG:5070")


def main() -> None:
    h = pd.read_csv(HAZ, low_memory=False)
    n1 = h["haz_wildfire_max_severity_1000m"] >= 4
    n24 = h["haz_wildfire_max_severity_2400m"] >= 4
    n5 = h["haz_wildfire_max_severity_5000m"] >= 4
    # Nested by construction; assert so a future data change fails loudly.
    assert not (n1 & ~n24).any() and not (n24 & ~n5).any(), "tiers not nested"
    tier = np.where(n1, 3, np.where(n24, 2, np.where(n5, 1, 0)))
    counts = [int((tier == k).sum()) for k in range(4)]

    fig = plt.figure(figsize=(15, 6.4))
    gs = GridSpec(1, 2, width_ratios=[2.15, 1], wspace=0.13,
                  left=0.02, right=0.97, top=0.78, bottom=0.09)

    # --- map -------------------------------------------------------------------
    ax = fig.add_subplot(gs[0, 0])
    base = _basemap()
    if base is not None:
        base.plot(ax=ax, color="#f2f2f0", edgecolor="#ffffff",
                  linewidth=0.6, zorder=1)

    pts = gpd.GeoDataFrame(
        h.assign(_t=tier),
        geometry=gpd.points_from_xy(h["longitude"], h["latitude"]),
        crs="EPSG:4326").to_crs("EPSG:5070")

    # Draw least-exposed first so the signal sits on top.
    for k, (color, size, z) in enumerate([
            (NONE_C, 5, 2), (RAMP[0], 9, 3), (RAMP[1], 13, 4), (RAMP[2], 20, 5)]):
        sel = pts[pts["_t"] == k]
        sel.plot(ax=ax, color=color, markersize=size, zorder=z,
                 linewidth=0.4 if k == 3 else 0,
                 edgecolor=SURFACE if k == 3 else "none")
    ax.set_axis_off()

    handles = [Line2D([0], [0], marker="o", linestyle="none",
                      markerfacecolor=c, markeredgecolor="none",
                      markersize=m, label=f"{lab}  ({n:,})")
               for c, m, lab, n in zip([NONE_C] + RAMP, [5, 6, 7.5, 9],
                                       LABELS, counts)]
    leg = ax.legend(handles=handles, loc="lower left", frameon=True,
                    fontsize=10.5, borderpad=0.7, labelspacing=0.5,
                    handletextpad=0.7,
                    title="Distance to High/Very-High wildfire land")
    leg.get_title().set_fontsize(10)
    leg.get_title().set_color(INK3)
    leg.get_frame().set_facecolor(SURFACE)
    leg.get_frame().set_edgecolor("#e2e2e0")
    for t in leg.get_texts():
        t.set_color(INK2)

    # --- bars ------------------------------------------------------------------
    ax2 = fig.add_subplot(gs[0, 1])
    radii = ["Within\n1 km", "Within\n2.4 km", "Within\n5 km"]
    vals = [int(n1.sum()), int(n24.sum()), int(n5.sum())]
    ypos = np.arange(3)[::-1]
    for y, v, c in zip(ypos, vals, RAMP[::-1]):
        ax2.barh(y, v, height=0.34, color=c, zorder=3)
        ax2.text(v + 16, y + 0.06, f"{v:,}", va="center", ha="left",
                 fontsize=15, color=INK, fontweight="bold")
        ax2.text(v + 16, y - 0.22, f"{100 * v / len(h):.0f}% of all",
                 va="center", ha="left", fontsize=9.5, color=INK3)

    ax2.set_yticks(ypos)
    ax2.set_yticklabels(radii, fontsize=11.5, color=INK2)
    ax2.set_xlim(0, max(vals) * 1.34)
    ax2.set_ylim(-0.75, 2.75)
    ax2.set_xticks([])
    ax2.tick_params(left=False)
    for s in ax2.spines.values():
        s.set_visible(False)
    ax2.set_title("Cumulative count within each radius",
                  fontsize=11.5, color=INK2, loc="left", pad=10)

    # --- titles ----------------------------------------------------------------
    fig.text(0.02, 0.945,
             "342 US data centers sit within 1 km of high wildfire hazard land",
             fontsize=20, fontweight="bold", color=INK, ha="left")
    fig.text(0.02, 0.885,
             f"All {len(h):,} facilities in the contiguous US, measured against "
             "USFS Wildfire Hazard Potential 2023 (270 m). Hazard is measured "
             "across the surrounding area, not the pixel under the building.",
             fontsize=11, color=INK3, ha="left")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=220, facecolor=SURFACE, bbox_inches="tight")
    print(f"saved {OUT.relative_to(REPO)}  tiers={counts}  radii={vals}")


if __name__ == "__main__":
    main()
