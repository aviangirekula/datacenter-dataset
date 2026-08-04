"""Build the ASSIP poster from the official template.

Starts from the program's own 36 x 27 inch template so the fixed elements stay
untouched (poster size and colour scheme may not be changed), then normalises
the column grid, replaces the placeholder text, and places the figures.

Grid corrections applied to the stock template, which is misaligned as shipped:
- every left edge snapped to 0.50, 12.35 or 24.20 in and every right edge to
  11.80, 23.65 or 35.50, so the green heading bars are exactly as wide as the
  white boxes beneath them (the template ships them 0.06 in narrower)
- the GMU logo moved off the trim edge and clear of the title bar, which it
  overlapped

    ./.venv/bin/python scripts/build_poster.py
"""
from __future__ import annotations

import copy
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = Path("/tmp/assip_template.pptx")
FIGS = REPO / "figures" / "poster"
OUT = REPO / "figures" / "Oughton_Avilash_Angirekula_2026ASSIP_Poster.pptx"

GREEN = RGBColor(0x00, 0x66, 0x00)
GOLD = RGBColor(0xFF, 0xCC, 0x00)
LGREY = RGBColor(0xE5, 0xE5, 0xE5)
BLACK = RGBColor(0x00, 0x00, 0x00)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

# Three-column grid. 0.50 + 11.30 + 0.55 + 11.30 + 0.55 + 11.30 + 0.50 = 36.00
COL = [0.50, 12.35, 24.20]
CW = 11.30
BODY_TOP = 4.95
BODY_BOT = 26.50
BAR_H = 0.95
def fig_height(name: str, width_in: float = 11.30) -> float:
    """Placed height for a figure, read from the image's real aspect ratio.

    Hardcoding these is what pushed two columns off the bottom of the page in an
    earlier build, and it silently goes stale whenever a figure is regenerated.
    """
    from PIL import Image
    with Image.open(FIGS / f"{name}.png") as im:
        w, h = im.size
    return width_in * h / w

TITLE = "Two Americas of Data Center Hazard: 2,696 US Facilities Mapped"
AUTHORS = "Avilash Angirekula¹, Dennies Bor¹, Edward J. Oughton¹"
AFFIL = ("¹Department of Geography and Geoinformation Sciences, "
         "College of Science, George Mason University")

BACKGROUND = (
    "Artificial intelligence and cloud computing have concentrated enormous "
    "computing capacity into a small number of US locations. Those buildings "
    "face earthquakes, wildfire, and flooding, but no open dataset records "
    "where they physically stand.\n\n"
    "Existing sources are proprietary, aggregated above the building level, or "
    "unverified. Without building-level locations, no one can measure what US "
    "computing infrastructure is exposed to.\n\n"
    "These are EXPOSURE values, not risk. No vulnerability term is applied, so "
    "nothing here is a damage or loss estimate."
)

METHODS = (
    "A reproducible Python pipeline merges OpenStreetMap, PeeringDB, and "
    "Wikidata, removes duplicate records, and grades every coordinate against "
    "an independent building-footprint dataset.\n\n"
    "Hazards are then read at each facility from official sources:"
)
METHODS_TABLE = [
    ("Earthquake", "USGS ASCE 7-22 point service"),
    ("Wildfire", "USFS Hazard Potential, 270 m"),
    ("Flood", "FEMA National Flood Hazard Layer"),
    ("Water stress", "WRI Aqueduct 4.0"),
]
METHODS_TAIL = (
    "Missing data is always recorded as unknown, never as zero. A facility "
    "counts as exposed if it sits within 2.4 km of land rated High or Very "
    "High for wildfire potential, inside a FEMA regulatory floodplain, or at "
    "peak ground acceleration of 0.30 g or more."
)

STATS = [("2,696", "facilities mapped"), ("1,681", "on a building footprint"),
         ("35%", "face a mapped hazard"), ("0.7%", "of Virginia's 409")]

RESULTS_LEAD = (
    "Hazard exposure is bimodal. It is decided by which cluster a facility "
    "sits in, not by anything about data centers."
)
RESULTS_BODY = (
    "Of 2,696 facilities, 1,742 face no mapped hazard and 205 face two or "
    "more. Eighteen states holding half the fleet sit below 10% exposed. Ten "
    "states holding a third sit above 60%.\n\n"
    "Virginia, the largest concentration on Earth, is 0.7% exposed. "
    "California and New Jersey are 100%.\n\n"
    "Water stress is the exception that reaches Virginia. 952 facilities "
    "nationally sit in high or extremely-high stress basins."
)
NULLS = (
    "Two things we expected and did not find\n"
    "Measuring hazard across the whole building footprint instead of one point "
    "changed the answer for only 8.9% of facilities. Building height showed no "
    "association with exposure once state was controlled, with a median "
    "difference of exactly 0.0 across 23 states."
)
BOUNDS = (
    "Bounds on these results\n"
    "•  Hail and wind rates track observer density (+0.39, +0.34 within "
    "state) and are excluded from every result shown.\n"
    "•  Power capacity is unrecorded for all 2,696, so every statistic is "
    "a facility count, not capacity.\n"
    "•  234 coordinates match a building only beyond 200 m. Under 500-draw "
    "positional error, 2,067 facilities never change class."
)

CONCLUSIONS = (
    "•  A national average describes no real facility. Exposure is "
    "concentrated in a nameable minority of places.\n\n"
    "•  The industry has clustered in the low-exposure half of the "
    "country. That is a finding about siting.\n\n"
    "•  Building height belongs in the vulnerability term, not the "
    "exposure term.\n\n"
    "•  Next: fragility curves for server and cooling equipment, to turn "
    "exposure into estimated loss."
)

CITATIONS = (
    "Dillon, G.K. (2023) Wildfire Hazard Potential for the United States, "
    "270-m, v2023. USDA Forest Service. doi:10.2737/RDS-2015-0047-4\n"
    "Petersen, M.D. et al. (2023) 2023 US National Seismic Hazard Model. USGS. "
    "doi:10.5066/P9GNPCOD\n"
    "FEMA (2026) National Flood Hazard Layer. hazards.fema.gov\n"
    "Oughton, E.J. & Weigel, R. (2026) A Comparative Multi-Hazard Risk "
    "Assessment of the US High-Voltage Transmission Network. Zenodo. "
    "doi:10.5281/zenodo.20331026 (CC BY 4.0)\n"
    "WRI (2023) Aqueduct 4.0 Water Risk Atlas."
)
ACK = (
    "Made possible by George Mason University's College of Science, which "
    "supports the ASSIP Program. Thanks to Prof. Edward Oughton for "
    "supervision and Dennies Bor for the multi-hazard layers.\n\n"
    "Data and code: github.com/aviangirekula/datacenter-dataset"
)


def fit_height(txt: str, size_pt: float, width_in: float,
               spacing: float = 0.95, space_after_pt: float = 10.0) -> float:
    """Height a text block actually needs, in inches.

    Sizing these by eye is what clipped five blocks in an earlier build: with
    autofit deliberately off, PowerPoint does not shrink to compensate, it just
    cuts the text off. Arial mixed case averages about 0.52 em per character.
    """
    usable = width_in - 0.20                      # left + right internal margin
    chars_per_line = max(int(usable / (0.52 * size_pt / 72.0)), 10)
    line_h = size_pt * spacing / 72.0
    total = 0.0
    for para in txt.split("\n"):
        n_lines = max(1, -(-len(para) // chars_per_line))
        total += n_lines * line_h + space_after_pt / 72.0
    return total + 0.12                            # top + bottom padding


def clear_slide(slide):
    """Remove every placeholder shape, keeping the blank themed slide."""
    for shp in list(slide.shapes):
        shp._element.getparent().remove(shp._element)


def box(slide, x, y, w, h, fill=None, line=None):
    from pptx.enum.shapes import MSO_SHAPE
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y),
                               Inches(w), Inches(h))
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1)
    s.shadow.inherit = False
    return s


def text(slide, x, y, w, h, runs, size=28, colour=BLACK, bold=False,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=0.95):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.10)
    tf.margin_top = tf.margin_bottom = Inches(0.05)
    lines = runs if isinstance(runs, list) else runs.split("\n")
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        p.space_after = Pt(10)
        r = p.add_run()
        r.text = ln
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = colour
        r.font.name = "Arial"
    return tb


def heading(slide, col_x, y, label):
    box(slide, col_x, y, CW, BAR_H, fill=GREEN)
    text(slide, col_x + 0.20, y + 0.06, CW - 0.30, BAR_H - 0.10, label,
         size=44, colour=WHITE, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    return y + BAR_H + 0.10


def main() -> None:
    prs = Presentation(str(TEMPLATE))
    assert abs(prs.slide_width.inches - 36) < 0.01, "template is not 36 in wide"
    assert abs(prs.slide_height.inches - 27) < 0.01, "template is not 27 in tall"
    slide = prs.slides[0]

    # Keep the two logo images, drop every placeholder text shape.
    pics = [s for s in slide.shapes if s.shape_type == 13]
    keep = [copy.deepcopy(p._element) for p in pics]
    clear_slide(slide)
    for el in keep:
        slide.shapes._spTree.append(el)
    # Reposition the GMU logo off the trim edge and clear of the title bar.
    for shp in slide.shapes:
        if shp.shape_type == 13:
            shp.left, shp.top = Inches(0.30), Inches(0.35)
            shp.width, shp.height = Inches(3.55), Inches(4.00)
            break

    # ---- header ----
    box(slide, 4.30, 0.40, 27.30, 2.55, fill=GREEN)
    text(slide, 4.45, 0.50, 27.00, 2.35, TITLE, size=88, colour=WHITE,
         bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, spacing=0.92)
    text(slide, 4.30, 3.02, 27.30, 0.95, AUTHORS, size=40, bold=True,
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(slide, 4.30, 3.95, 27.30, 0.72, AFFIL, size=26, colour=RGBColor(0x44, 0x44, 0x44),
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    box(slide, 0.50, 4.78, 35.00, 0.06, fill=GOLD)

    # ---- column 1: Background, Methods ----
    y = heading(slide, COL[0], BODY_TOP, "Background")
    bh = fit_height(BACKGROUND, 28, CW)
    text(slide, COL[0], y, CW, bh, BACKGROUND, size=28)
    y = heading(slide, COL[0], 12.85, "Materials and Methods")
    mh = fit_height(METHODS, 28, CW)
    text(slide, COL[0], y, CW, mh, METHODS, size=28)
    ty = y + mh
    for name, src in METHODS_TABLE:
        box(slide, COL[0] + 0.10, ty, CW - 0.20, 0.78, fill=LGREY,
            line=RGBColor(0xA5, 0xA5, 0xA5))
        text(slide, COL[0] + 0.25, ty + 0.06, 3.30, 0.66, name, size=26, bold=True,
             anchor=MSO_ANCHOR.MIDDLE)
        text(slide, COL[0] + 3.55, ty + 0.06, CW - 3.85, 0.66, src, size=24,
             colour=RGBColor(0x33, 0x33, 0x33), anchor=MSO_ANCHOR.MIDDLE)
        ty += 0.90
    th = fit_height(METHODS_TAIL, 28, CW)
    text(slide, COL[0], ty + 0.10, CW, th, METHODS_TAIL, size=28)

    # Limitations sit at the foot of Methods rather than in Conclusions, so the
    # poster does not end on a caveat and column 3 stays on the page.
    bnh = fit_height(BOUNDS, 20, CW - 0.45)
    by = ty + th + 0.35
    box(slide, COL[0], by, CW, bnh + 0.14, fill=LGREY, line=RGBColor(0xA5, 0xA5, 0xA5))
    box(slide, COL[0], by, 0.14, bnh + 0.14, fill=GOLD)
    text(slide, COL[0] + 0.25, by + 0.06, CW - 0.45, bnh, BOUNDS, size=20)

    # ---- column 2: Results ----
    y = heading(slide, COL[1], BODY_TOP, "Results")

    # stat strip
    sw = (CW - 0.30) / 4
    for i, (num, lab) in enumerate(STATS):
        x = COL[1] + 0.05 + i * (sw + 0.05)
        text(slide, x, y, sw, 0.85, num, size=54, bold=True,
             align=PP_ALIGN.CENTER, colour=GREEN)
        text(slide, x, y + 0.82, sw, 0.75, lab, size=19,
             colour=RGBColor(0x44, 0x44, 0x44), align=PP_ALIGN.CENTER)
    y += 1.58

    lh = fit_height(RESULTS_LEAD, 31, CW)
    text(slide, COL[1], y, CW, lh, RESULTS_LEAD, size=31, bold=True)
    y += lh + 0.12
    slide.shapes.add_picture(str(FIGS / "fig1_map.png"), Inches(COL[1]),
                             Inches(y), width=Inches(CW))
    y += fig_height("fig1_map") + 0.15
    cap = ("Fig 1. Two thirds of US data centers face no mapped hazard. "
           "Exposure is regional, not universal.")
    chh = fit_height(cap, 24, CW)
    text(slide, COL[1], y, CW, chh, cap, size=24, bold=True)
    y += chh + 0.10
    rh = fit_height(RESULTS_BODY, 28, CW)
    text(slide, COL[1], y, CW, rh, RESULTS_BODY, size=28)
    y += rh + 0.12
    slide.shapes.add_picture(str(FIGS / "fig2_states.png"), Inches(COL[1]),
                             Inches(y), width=Inches(CW))
    y += fig_height("fig2_states") + 0.15
    cap = "Fig 2. States split into two groups with almost nothing between them."
    text(slide, COL[1], y, CW, fit_height(cap, 24, CW), cap, size=24, bold=True)

    # ---- column 3: Conclusions, Citations, Acknowledgements ----
    # A heading must be followed by its own content. An earlier version put the
    # coordinate-quality figure directly under "Conclusions", which read as if
    # the figure were a conclusion.
    y = heading(slide, COL[2], BODY_TOP, "Conclusions")
    ch = fit_height(CONCLUSIONS, 27, CW)
    text(slide, COL[2], y, CW, ch, CONCLUSIONS, size=27)
    y += ch + 0.12

    nh = fit_height(NULLS, 23, CW - 0.45)
    box(slide, COL[2], y, CW, nh + 0.16, fill=LGREY, line=RGBColor(0xA5, 0xA5, 0xA5))
    box(slide, COL[2], y, 0.14, nh + 0.16, fill=GOLD)
    text(slide, COL[2] + 0.25, y + 0.08, CW - 0.45, nh, NULLS, size=23)
    y += nh + 0.30

    slide.shapes.add_picture(str(FIGS / "fig3_confidence.png"), Inches(COL[2]),
                             Inches(y), width=Inches(CW))
    y += fig_height("fig3_confidence") + 0.12
    cap = ("Fig 3. Coordinate quality was measured, not assumed. Results stay "
           "stable under realistic positional error.")
    text(slide, COL[2], y, CW, fit_height(cap, 24, CW), cap, size=24, bold=True)

    y = heading(slide, COL[2], y, "Major Citations")
    cth = fit_height(CITATIONS, 19, CW, spacing=0.90)
    text(slide, COL[2], y, CW, cth, CITATIONS, size=19,
         colour=RGBColor(0x33, 0x33, 0x33), spacing=0.90)
    y += cth + 0.12
    y = heading(slide, COL[2], y, "Acknowledgements")
    ah = fit_height(ACK, 21, CW)
    text(slide, COL[2], y, CW, ah, ACK, size=21,
         colour=RGBColor(0x33, 0x33, 0x33))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUT))
    print(f"Wrote {OUT.relative_to(REPO)}")
    print(f"  slide: {prs.slide_width.inches:.0f} x {prs.slide_height.inches:.0f} in")
    print(f"  shapes: {len(slide.shapes)}")


if __name__ == "__main__":
    main()
