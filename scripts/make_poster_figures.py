"""Build the poster figures at exact printed size.

Each figure is created at the physical dimensions it will occupy on a 36 x 27
inch poster. Export trims to the ink, so each figure lands at its own scale on
the sheet and a nominal point size is not the printed size. Nominal sizes here
are set so the measured printed size clears the template's 20 pt floor; see the
check at the end of main(), which fails the build if any figure drops below it.

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
PURPLE = "#CC79A7"      # Okabe-Ito, unused by fig 1
GREY_MAP = "#9E9E9E"    # same grey fig 1 uses for the same meaning
INK, INK2, INK3 = "#1a1a1a", "#4a4a4a", "#6e6e6e"

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "figure.facecolor": "white", "axes.facecolor": "white",
    "savefig.facecolor": "white",
})


def save_at(fig, name: str, placed_w_in: float) -> None:
    """Save trimmed, then resample so the placed scale is exactly 1.0.

    bbox_inches="tight" is required (otherwise titles and legends outside the
    axes are clipped), but it trims to the ink so the saved width varies per
    figure. Forcing the width to DPI * placed_w_in makes nominal point sizes
    equal printed point sizes, and keeps every figure at exactly DPI.
    """
    from PIL import Image
    path = OUT / f"{name}.png"
    fig.savefig(path, dpi=DPI, bbox_inches="tight", pad_inches=0.14)
    target = int(round(DPI * placed_w_in))
    with Image.open(path) as im:
        if im.size[0] != target:
            h = int(round(im.size[1] * target / im.size[0]))
            im.resize((target, h), Image.LANCZOS).save(path)


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
    fig, ax = plt.subplots(figsize=(10.70, 6.00))
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
                    fontsize=20, color=INK, fontweight="bold", ha="left",
                    linespacing=1.35,
                    arrowprops=dict(arrowstyle="-", color=INK2, lw=1.6))
    ca = pts[pts["state"] == "CA"]
    if len(ca):
        x, y = ca.geometry.x.median(), ca.geometry.y.median()
        ax.annotate("California\n223 facilities\n100% exposed",
                    xy=(x, y), xytext=(x - 2.0e5, y + 7.2e5),
                    fontsize=20, color=VERM, fontweight="bold", ha="right",
                    linespacing=1.35,
                    arrowprops=dict(arrowstyle="-", color=VERM, lw=1.6))

    fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.09)
    save_at(fig, "fig1_map", 11.79)
    plt.close(fig)
    print(f"  fig1_map.png  {counts}")


# --- Figure 2: state bars ------------------------------------------------------

def fig_states(d: pd.DataFrame) -> None:
    """How the fleet distributes across state exposure rates.

    Two earlier versions failed. The first plotted only the 7 lowest and 7
    highest of 32 states, which deleted Texas and 43% of the fleet and asserted
    a gap it had created. The second was a dot plot, but five states sit at
    exactly 0% and two at exactly 100%, so avoiding overlap meant stacking dots
    vertically, and that height encoded nothing while looking like it did.

    A histogram has no such problem: height is facilities, width is an exposure
    band, and nothing can occlude anything.
    """
    g = d.groupby("state").agg(
        n=("facility_id", "size"),
        pct=("n_haz", lambda s: 100 * (s >= 1).mean()),
        fire=("f_fire", "mean"), flood=("f_flood", "mean"),
        quake=("f_quake", "mean")).query("n >= 20")
    n_all, N = len(g), len(d)
    mid = (g["pct"] >= 10) & (g["pct"] <= 60)
    mid_n, mid_share = int(mid.sum()), 100 * g.loc[mid, "n"].sum() / N

    # For a state at 0.7% exposed, "dominant hazard" is the argmax of three
    # near-zero numbers, so Virginia's 409 facilities were being coloured
    # flood-driven. States under 1% get their own category instead.
    drivers = g[["fire", "flood", "quake"]].idxmax(axis=1)
    drivers[g["pct"] < 1] = "none"
    edges = np.arange(0, 101, 10)
    keys = ["none", "fire", "quake", "flood"]
    cmap = {"none": GREY_MAP, "fire": ORANGE, "quake": TEAL, "flood": PURPLE}
    names = {"none": "Under 1% exposed", "fire": "Wildfire-driven",
             "quake": "Earthquake-driven", "flood": "Flood-driven"}

    stacks = {k: [] for k in keys}
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (g["pct"] >= lo) & ((g["pct"] < hi) if hi < 100 else (g["pct"] <= 100))
        for k in keys:
            stacks[k].append(int(g.loc[sel & (drivers == k), "n"].sum()))

    fig, ax = plt.subplots(figsize=(10.70, 3.55))
    x = edges[:-1] + 5
    bottom = np.zeros(len(x))
    for k in keys:
        v = np.array(stacks[k], dtype=float)
        ax.bar(x, v, bottom=bottom, width=9.2, color=cmap[k], zorder=3,
               edgecolor="white", linewidth=1.0, label=names[k])
        bottom += v

    for xi, tot in zip(x, bottom):
        if tot:
            ax.text(xi, tot + 22, f"{int(tot):,}", ha="center", fontsize=20,
                    color=INK, fontweight="bold")

    ax.set_xlim(-2, 102)
    ax.set_ylim(0, bottom.max() * 1.30)
    ax.set_xticks(edges)
    ax.set_xticklabels([f"{e}%" for e in edges], fontsize=20)
    ax.tick_params(axis="x", labelsize=20, colors=INK2)
    ax.get_yaxis().set_visible(False)
    ax.set_xlabel("Share of a state's facilities facing at least one mapped hazard",
                  fontsize=21, color=INK2, labelpad=10)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color("#cccccc")

    ax.set_title(f"Facilities by their state's exposure rate, all {n_all} states "
                 f"with 20 or more.\nOnly {mid_n} states fall between 10% and 60%, "
                 f"holding {mid_share:.0f}% of the fleet.",
                 fontsize=21, color=INK, loc="left", pad=14, linespacing=1.4)
    leg = ax.legend(loc="upper center", ncol=4, frameon=False, fontsize=20,
                    bbox_to_anchor=(0.5, -0.42), handletextpad=0.8,
                    columnspacing=1.8)
    for t in leg.get_texts():
        t.set_color(INK2)

    fig.subplots_adjust(left=0.015, right=0.99, top=0.80, bottom=0.34)
    save_at(fig, "fig2_states", 11.79)
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

    fig, ax = plt.subplots(figsize=(10.70, 2.55))
    ax.plot(xs, ys, lw=2.6, color=ORANGE, zorder=3, solid_capstyle="round")
    ax.scatter(xs, ys, s=[150 if s else 90 for s in solid], zorder=4,
               color=[ORANGE if s else "white" for s in solid],
               edgecolor=ORANGE, linewidth=2.4)

    for x, v, n, s in zip(xs, ys, ns, solid):
        ax.annotate(f"{v:.0f}%\nn={n:,}", (x, v), xytext=(0, 20),
                    textcoords="offset points", ha="center", fontsize=20,
                    color=INK if s else INK3, fontweight="bold",
                    linespacing=1.25)

    ax.set_xscale("log")
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{x} m" for x in xs], fontsize=20)
    ax.tick_params(axis="both", labelsize=20, colors=INK2, which="both")
    ax.minorticks_off()
    ax.set_xlim(8, 640)
    ax.set_ylim(0, max(ys) * 1.95)
    ax.set_ylabel("Sites changing class (%)", fontsize=20, color=INK2)
    ax.set_xlabel("Positional uncertainty (log scale)",
                  fontsize=20, color=INK2, labelpad=10)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#cccccc")
    ax.set_title("Chance that one relocation flips a site's wildfire class.\n"
                 "Hollow points rest on under 100 sites.",
                 fontsize=20, color=INK, loc="left", pad=16, linespacing=1.4)

    fig.subplots_adjust(left=0.115, right=0.985, top=0.74, bottom=0.22)
    save_at(fig, "fig3_confidence", 11.37)
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
