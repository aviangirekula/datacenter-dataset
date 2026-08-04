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
# 340, not 300: bbox_inches='tight' trims to the drawn extent, so the saved
# width is a little under figsize and the placed resolution lands just below
# 300 dpi at the column width the template gives us.
DPI = 340

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
    # FEMA does not map every county and a few buffers return no wildfire value.
    # Those facilities fall into n_haz == 0 by construction, so track them and
    # say so rather than letting them read as verified-clear.
    d["unmapped_input"] = (d["flood_sfha"].isna()
                           | d["haz_wildfire_max_severity_2400m"].isna())
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
    fig, ax = plt.subplots(figsize=(10.70, 6.30))
    base = basemap()
    if base is not None:
        base.plot(ax=ax, color="#f4f4f2", edgecolor="white", linewidth=0.8, zorder=1)

    pts = gpd.GeoDataFrame(
        d, geometry=gpd.points_from_xy(d["longitude"], d["latitude"]),
        crs="EPSG:4326").to_crs("EPSG:5070")

    # Least-exposed drawn first so the signal sits on top.
    # markersize is AREA in pt^2, so these are diameters of 6.0, 8.0 and 11.0 pt.
    # The previous 9/16/30 printed at 1.1-1.9 mm, below hue discrimination at
    # poster distance. ORANGE became BLUE: orange and vermillion are the closest
    # pair in Okabe-Ito and converge further for red-green colour vision.
    spec = [(0, "#9E9E9E", 49, "No mapped hazard"),
            (1, BLUE, 64, "One hazard"),
            (2, VERM, 121, "Two or more")]
    for n, colour, size, _ in spec:
        sel = pts[pts["n_haz"] == n] if n < 2 else pts[pts["n_haz"] >= 2]
        sel.plot(ax=ax, color=colour, markersize=size, zorder=2 + n,
                 linewidth=0.5 if n == 2 else 0,
                 edgecolor="white" if n == 2 else "none")
    ax.set_axis_off()

    counts = [int((d["n_haz"] == 0).sum()), int((d["n_haz"] == 1).sum()),
              int((d["n_haz"] >= 2).sum())]
    # Reported in the poster's limitations panel rather than crammed into the
    # legend, where it read as qualifying the wrong category.
    print(f"    {int((d['unmapped_input'] & (d['n_haz'] == 0)).sum())} of the "
          f"no-hazard facilities have an unmapped input")
    handles = [Line2D([0], [0], marker="o", linestyle="none", markerfacecolor=c,
                      markeredgecolor="none", markersize=np.sqrt(size),
                      label=f"{lab}  ({n:,})")
               for (_, c, size, lab), n in zip(spec, counts)]  # sqrt: area -> dia

    leg = ax.legend(handles=handles, loc="upper center", ncol=3, frameon=False,
                    bbox_to_anchor=(0.5, 0.045), fontsize=20,
                    handletextpad=0.9, columnspacing=3.0)
    leg.set_zorder(20)
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

    fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.09)
    fig.savefig(OUT / "fig1_map.png", dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  fig1_map.png  {counts}")


# --- Figure 2: state bars ------------------------------------------------------

def fig_states(d: pd.DataFrame) -> None:
    """Every state with 20 or more facilities, on one axis.

    An earlier version plotted only the 7 lowest and 7 highest of 32 states and
    then annotated the empty middle. That deleted Texas (n=230, larger than
    California) along with 43% of the fleet, and it asserted the gap rather than
    showing it. Plotting all 32 lets the reader see the shape and check it.
    """
    g = d.groupby("state").agg(
        n=("facility_id", "size"),
        pct=("n_haz", lambda s: 100 * (s >= 1).mean()),
        fire=("f_fire", "mean"), flood=("f_flood", "mean"),
        quake=("f_quake", "mean")).query("n >= 20").sort_values("pct")
    n_all, N = len(g), len(d)
    mid = (g["pct"] >= 10) & (g["pct"] <= 60)
    mid_n, mid_share = int(mid.sum()), 100 * g.loc[mid, "n"].sum() / N

    fig, ax = plt.subplots(figsize=(10.70, 4.05))
    # Colour by which hazard drives the state, because "100%" means wildfire in
    # New Jersey and earthquake in California, and the poster should say so.
    drivers = g[["fire", "flood", "quake"]].idxmax(axis=1)
    cmap = {"fire": ORANGE, "flood": BLUE, "quake": TEAL}
    ax.scatter(g["pct"], np.zeros(n_all), s=g["n"] * 1.9, zorder=3, alpha=0.80,
               color=[GREY if p < 1 else cmap[k] for p, k in zip(g["pct"], drivers)],
               edgecolor="white", linewidth=1.2)

    # Labels sit in two staggered rows ABOVE the axis only. Placing some below
    # pushed them into the x-axis title, and a single row collided wherever two
    # states sat close together (OH 0.0% vs VA 0.7%, AZ 98.8% vs CA 100%).
    label = ["VA", "TX", "FL", "NV", "WA", "OR", "AZ", "CA"]
    for i, st in enumerate(sorted(label, key=lambda s: g.loc[s, "pct"])):
        ax.annotate(f"{st}  n={int(g.loc[st, 'n'])}", (g.loc[st, "pct"], 0),
                    xytext=(0, 82 if i % 2 == 0 else 38),
                    textcoords="offset points", fontsize=19, color=INK,
                    ha="center", va="bottom",
                    arrowprops=dict(arrowstyle="-", color="#c9c9c9", lw=1.1,
                                    shrinkA=1, shrinkB=8))

    ax.set_xlim(-6, 106)
    ax.set_ylim(-0.42, 1.58)
    ax.get_yaxis().set_visible(False)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"])
    ax.tick_params(axis="x", labelsize=19, colors=INK2)
    ax.set_xlabel("Facilities facing at least one mapped hazard (%)",
                  fontsize=21, color=INK2, labelpad=10)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#cccccc")

    ax.set_title(f"All {n_all} states with 20 or more facilities. Dot size = "
                 f"facility count.\nOnly {mid_n} sit between 10% and 60%, "
                 f"holding {mid_share:.0f}% of all facilities.",
                 fontsize=20, color=INK, loc="left", pad=16, linespacing=1.4)
    handles = [Line2D([0], [0], marker="o", linestyle="none", markersize=11,
                      markerfacecolor=c, markeredgecolor="none", label=lab)
               for c, lab in ((ORANGE, "Wildfire-driven"), (TEAL, "Earthquake-driven"),
                              (BLUE, "Flood-driven"), (GREY, "Under 1% exposed"))]
    leg = ax.legend(handles=handles, loc="upper center", ncol=4, frameon=False,
                    fontsize=19, bbox_to_anchor=(0.5, -0.42), handletextpad=0.6,
                    columnspacing=1.9)
    for t in leg.get_texts():
        t.set_color(INK2)

    fig.subplots_adjust(left=0.03, right=0.99, top=0.82, bottom=0.30)
    fig.savefig(OUT / "fig2_states.png", dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  fig2_states.png  all {n_all} states, {mid_n} in the middle band")


# --- Figure 3: coordinate confidence + stability -------------------------------

def fig_confidence(d: pd.DataFrame) -> None:
    """How far wildfire class moves under each tier's own positional error.

    Three deliberate changes from the earlier version:
    - the stacked "how each coordinate resolved" panel is gone. It drew three
      integers, one of which is already a 48 pt headline statistic, and its
      0.8% "no match" sliver was too small to label honestly.
    - x is metres, a continuous quantity, so this is a line on a log axis. Drawn
      as equal-width bars, the 250 m and 500 m steps looked like the 10 m step
      and manufactured a plateau.
    - the per-tier n is back. The two rightmost points rest on 29 and 8
      facilities, which is the only thing that decides whether they mean
      anything, and it had been dropped for looking untidy.
    """
    unc = json.load(open(P / "coordinate_uncertainty.json"))
    tiers = unc["by_tier"]
    xs = [int(k.split("_")[1].replace("m", "")) for k in tiers]
    ys = [100 * v["mean_whp_change_prob"] for v in tiers.values()]
    ns = [v["n"] for v in tiers.values()]
    order = np.argsort(xs)
    xs, ys, ns = ([v[i] for i in order] for v in (xs, ys, ns))
    solid = [n >= 100 for n in ns]

    fig, ax = plt.subplots(figsize=(10.70, 2.80))
    ax.plot(xs, ys, lw=2.6, color=ORANGE, zorder=3, solid_capstyle="round")
    ax.scatter(xs, ys, s=[150 if s else 90 for s in solid], zorder=4,
               color=[ORANGE if s else "white" for s in solid],
               edgecolor=ORANGE, linewidth=2.4)

    for x, v, n, s in zip(xs, ys, ns, solid):
        ax.annotate(f"{v:.0f}%\nn={n:,}", (x, v), xytext=(0, 20),
                    textcoords="offset points", ha="center", fontsize=19,
                    color=INK if s else INK3, fontweight="bold",
                    linespacing=1.25)

    ax.set_xscale("log")
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{x} m" for x in xs], fontsize=19)
    ax.tick_params(axis="both", labelsize=19, colors=INK2, which="both")
    ax.minorticks_off()
    ax.set_xlim(8, 640)
    ax.set_ylim(0, max(ys) * 1.95)
    ax.set_ylabel("Sites changing class (%)", fontsize=19, color=INK2)
    ax.set_xlabel("Positional uncertainty (log scale)",
                  fontsize=20, color=INK2, labelpad=10)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#cccccc")
    ax.set_title("Wildfire class changes for 1-9% of sites located to 100 m or "
                 "better.\nHollow points rest on under 100 sites.",
                 fontsize=20, color=INK, loc="left", pad=16, linespacing=1.4)

    fig.subplots_adjust(left=0.115, right=0.985, top=0.74, bottom=0.22)
    fig.savefig(OUT / "fig3_confidence.png", dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  fig3_confidence.png  n per tier {ns}")


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
