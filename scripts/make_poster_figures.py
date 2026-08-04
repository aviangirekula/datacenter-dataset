"""Build the poster figures at exact printed size.

Each figure is created at the physical dimensions it will occupy on a 36 x 27
inch poster and exported at 300 dpi, so a 20 pt label in this code is genuinely
20 pt on the printed sheet. Exporting small and stretching in PowerPoint would
shrink every font relative to the page.

Hazard flags, all source-anchored rather than quantile-defined:
- wildfire: USFS WHP class 4 or 5 (High / Very High) within 2.4 km
- flood:    inside a FEMA Special Flood Hazard Area
- seismic:  USGS ASCE 7-22 MCE_G peak ground acceleration >= 0.3 g

    ./.venv/bin/python scripts/make_poster_figures.py
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

REPO = Path(__file__).resolve().parents[1]
P = REPO / "data" / "processed"
OUT = REPO / "figures" / "poster"
DPI = 300

# Okabe-Ito, chosen for colourblind safety and kept deliberately distinct from
# the fixed template palette so a reader never confuses data with page chrome.
GREY = "#BDBDBD"
ORANGE = "#E69F00"
VERM = "#D55E00"
BLUE = "#0072B2"
TEAL = "#009E73"
INK, INK2, INK3 = "#1a1a1a", "#4a4a4a", "#6e6e6e"

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "figure.facecolor": "white", "axes.facecolor": "white",
    "savefig.facecolor": "white",
})


def load() -> pd.DataFrame:
    h = pd.read_csv(P / "hazard_exposure.csv", low_memory=False)
    b = pd.read_csv(P / "building_attributes.csv", low_memory=False)
    d = h.merge(b[["facility_id", "flood_sfha", "building_match"]],
                on="facility_id", how="left")
    d["f_fire"] = (d["haz_wildfire_max_severity_2400m"] >= 4).fillna(False)
    d["f_flood"] = (d["flood_sfha"] == True)          # noqa: E712 - NaN is not True
    d["f_quake"] = (d["haz_seismic_pga_g_2475yr_usgs"] >= 0.3).fillna(False)
    d["n_haz"] = d[["f_fire", "f_flood", "f_quake"]].sum(axis=1)
    return d


def basemap():
    county = REPO / "data" / "raw" / "tiger" / "tl_2024_us_county.shp"
    if not county.exists():
        return None
    g = gpd.read_file(county, columns=["STATEFP", "geometry"])
    g = g[~g["STATEFP"].isin({"02", "15", "60", "66", "69", "72", "78"})]
    return g.dissolve(by="STATEFP").to_crs("EPSG:5070")


# --- Figure 1: the map ---------------------------------------------------------

def fig_map(d: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10.70, 6.00))
    base = basemap()
    if base is not None:
        base.plot(ax=ax, color="#f4f4f2", edgecolor="white", linewidth=0.8, zorder=1)

    pts = gpd.GeoDataFrame(
        d, geometry=gpd.points_from_xy(d["longitude"], d["latitude"]),
        crs="EPSG:4326").to_crs("EPSG:5070")

    # Least-exposed drawn first so the signal sits on top.
    spec = [(0, GREY, 9, "No mapped hazard"),
            (1, ORANGE, 16, "One hazard"),
            (2, VERM, 30, "Two or more")]
    for n, colour, size, _ in spec:
        sel = pts[pts["n_haz"] == n] if n < 2 else pts[pts["n_haz"] >= 2]
        sel.plot(ax=ax, color=colour, markersize=size, zorder=2 + n,
                 linewidth=0.5 if n == 2 else 0,
                 edgecolor="white" if n == 2 else "none")
    ax.set_axis_off()

    counts = [int((d["n_haz"] == 0).sum()), int((d["n_haz"] == 1).sum()),
              int((d["n_haz"] >= 2).sum())]
    handles = [Line2D([0], [0], marker="o", linestyle="none", markerfacecolor=c,
                      markeredgecolor="none", markersize=m,
                      label=f"{lab}  ({n:,})")
               for (_, c, _, lab), m, n in zip(spec, [8, 10, 13], counts)]
    leg = ax.legend(handles=handles, loc="lower left", frameon=True, fontsize=20,
                    borderpad=0.7, labelspacing=0.5, handletextpad=0.8)
    leg.get_frame().set_edgecolor("#dddddd")
    for t in leg.get_texts():
        t.set_color(INK2)

    # Annotate the punchline directly on the map.
    va = pts[pts["state"] == "VA"]
    if len(va):
        x, y = va.geometry.x.median(), va.geometry.y.median()
        ax.annotate("Virginia\n409 facilities (15% of US)\n0.7% exposed",
                    xy=(x, y), xytext=(x + 5.2e5, y - 6.5e5),
                    fontsize=19, color=INK, fontweight="bold", ha="left",
                    linespacing=1.35,
                    arrowprops=dict(arrowstyle="-", color=INK2, lw=1.6))
    ca = pts[pts["state"] == "CA"]
    if len(ca):
        x, y = ca.geometry.x.median(), ca.geometry.y.median()
        ax.annotate("California\n223 facilities\n100% exposed",
                    xy=(x, y), xytext=(x - 2.0e5, y + 7.2e5),
                    fontsize=19, color=VERM, fontweight="bold", ha="right",
                    linespacing=1.35,
                    arrowprops=dict(arrowstyle="-", color=VERM, lw=1.6))

    fig.tight_layout(pad=0.4)
    fig.savefig(OUT / "fig1_map.png", dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  fig1_map.png  {counts}")


# --- Figure 2: state bars ------------------------------------------------------

def fig_states(d: pd.DataFrame) -> None:
    g = d.groupby("state").agg(n=("facility_id", "size"),
                               pct=("n_haz", lambda s: 100 * (s >= 1).mean()))
    g = g[g["n"] >= 20].sort_values("pct")
    # Show the extremes, which is where the story is.
    show = pd.concat([g.head(7), g.tail(7)])

    fig, ax = plt.subplots(figsize=(10.70, 5.60))
    y = np.arange(len(show))
    colours = [VERM if p > 60 else ORANGE if p > 10 else GREY for p in show["pct"]]
    ax.barh(y, show["pct"], height=0.72, color=colours, zorder=3)

    for i, (st, row) in enumerate(show.iterrows()):
        # One decimal below 10% so Virginia reads 0.7, matching the headline.
        pct = row["pct"]
        lab = f"{pct:.0f}%" if pct >= 10 else f"{pct:.1f}%"
        ax.text(pct + 1.8, i, lab, va="center",
                fontsize=19, color=INK, fontweight="bold")
        ax.text(-2.0, i, f"{st}", va="center", ha="right", fontsize=20, color=INK2)
        ax.text(-9.5, i, f"n={int(row['n'])}", va="center", ha="right",
                fontsize=17, color=INK3)

    ax.set_yticks([])
    ax.set_xlim(0, 118)
    ax.set_xlabel("Facilities facing at least one mapped hazard (%)",
                  fontsize=21, color=INK2, labelpad=10)
    ax.tick_params(axis="x", labelsize=19, colors=INK2)
    ax.set_ylim(-0.9, len(show) - 0.1)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#cccccc")
    ax.set_xticks([0, 25, 50, 75, 100])

    # The gap between the two groups IS the finding. Arrows collided with the
    # bar labels, so the callouts are placed in the empty space instead.
    n_show = len(show)
    mid = n_show / 2 - 0.5
    ax.axhline(mid, color="#bbbbbb", lw=1.4, ls=(0, (5, 4)), zorder=1)

    ax.text(50, mid - 1.15, "No state sits between 3% and 75%",
            va="center", ha="left", fontsize=20, color=INK, fontweight="bold")
    ax.text(50, mid - 2.15,
            "Virginia alone holds 409 facilities,\n"
            "15% of every data center in the US",
            va="top", ha="left", fontsize=18, color=INK2, linespacing=1.4)
    fig.subplots_adjust(left=0.16, right=0.98, top=0.97, bottom=0.16)
    fig.savefig(OUT / "fig2_states.png", dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  fig2_states.png  {len(show)} states shown")


# --- Figure 3: coordinate confidence + stability -------------------------------

def fig_confidence(d: pd.DataFrame) -> None:
    b = pd.read_csv(P / "building_attributes.csv", low_memory=False)
    unc = json.load(open(P / "coordinate_uncertainty.json"))
    fig, axes = plt.subplots(1, 2, figsize=(10.70, 4.20),
                             gridspec_kw={"width_ratios": [1.05, 1]})

    # Left: how coordinates resolved. Direct-labelled rather than using a
    # legend, which previously overlapped the bar itself.
    ax = axes[0]
    vc = b["building_match"].value_counts()
    labels = ["Inside a building", "Nearest building", "No match"]
    vals = [int(vc.get("contains", 0)), int(vc.get("nearest", 0)),
            int(vc.get("none", 0))]
    cols = [TEAL, BLUE, GREY]
    total = sum(vals)
    left = 0
    for v, c, lab in zip(vals, cols, labels):
        ax.barh(0, v, left=left, color=c, height=0.42, zorder=3)
        if v > 400:
            ax.text(left + v / 2, 0, f"{v:,}", ha="center", va="center",
                    color="white", fontsize=23, fontweight="bold")
            ax.text(left + v / 2, -0.36, lab, ha="center", va="top",
                    fontsize=18, color=INK2)
        left += v
    # The 22 unmatched are too small to label in place.
    ax.annotate(f"No match ({vals[2]})", xy=(total - vals[2] / 2, 0.22),
                xytext=(total * 0.90, 0.62), fontsize=17, color=INK3,
                ha="center", arrowprops=dict(arrowstyle="-", color="#bbbbbb", lw=1.2))
    ax.set_xlim(0, total)
    ax.set_ylim(-0.85, 0.85)
    ax.axis("off")
    ax.set_title("How each coordinate resolved", fontsize=21, color=INK2,
                 loc="left", pad=14)

    # Right: stability under positional error
    ax2 = axes[1]
    tiers = unc["by_tier"]
    xs = [int(k.split("_")[1].replace("m", "")) for k in tiers]
    ys = [100 * v["mean_whp_change_prob"] for v in tiers.values()]
    ns = [v["n"] for v in tiers.values()]
    order = np.argsort(xs)
    xs = [xs[i] for i in order]; ys = [ys[i] for i in order]; ns = [ns[i] for i in order]
    ax2.bar(range(len(xs)), ys, width=0.62, color=BLUE, zorder=3)
    for i, v in enumerate(ys):
        # n dropped: it collided with the tick labels and adds nothing the
        # reader needs at poster distance.
        ax2.text(i, v + 0.9, f"{v:.0f}%", ha="center", fontsize=19,
                 color=INK, fontweight="bold")
    ax2.set_xticks(range(len(xs)))
    ax2.set_xticklabels([f"{x} m" for x in xs], fontsize=18, color=INK2)
    ax2.set_ylabel("Hazard class changes (%)", fontsize=19, color=INK2)
    ax2.set_xlabel("Coordinate uncertainty", fontsize=19, color=INK2, labelpad=10)
    ax2.tick_params(axis="y", labelsize=17, colors=INK2)
    ax2.set_ylim(0, max(ys) * 1.28)
    for s in ("top", "right"):
        ax2.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax2.spines[s].set_color("#cccccc")
    ax2.set_title("Result stability under coordinate error", fontsize=21,
                  color=INK2, loc="left", pad=12)

    fig.tight_layout(pad=1.0)
    fig.savefig(OUT / "fig3_confidence.png", dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  fig3_confidence.png  {vals}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    d = load()
    n = len(d)
    print(f"facilities {n} | >=1 hazard {int((d['n_haz']>=1).sum())} "
          f"({100*(d['n_haz']>=1).mean():.1f}%)")
    fig_map(d)
    fig_states(d)
    fig_confidence(d)
    print(f"\nWrote figures to {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
