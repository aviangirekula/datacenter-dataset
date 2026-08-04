# Full Context Handoff — US Data Center Multi-Hazard Dataset & ASSIP Poster

**Written:** 2026-08-04, ~14:30 EDT
**Author of this file:** Claude (Opus 5), handing off to a fresh chat
**Owner:** Avilash Angirekula ("Avi")

---

## READ THIS FIRST (orientation)

1. Avilash Angirekula is a high-school student (Thomas Jefferson High School for Science and Technology) doing a summer research internship at **George Mason University** through **ASSIP** (Aspiring Scientists Summer Internship Program), summer 2026.
2. His project: build the **first open, building-level dataset of US data centers** and measure their **natural-hazard exposure**. 2,696 facilities across the contiguous US.
3. The code lives at `/Users/avilash/datacenter-dataset` (local) and `https://github.com/aviangirekula/datacenter-dataset` (public GitHub).
4. **The immediate deliverable is an ASSIP conference poster.** It was due on Canvas **Tuesday 2026-08-04 at 5:00 PM**. As of this file being written it is finished and exported; Avi may or may not have submitted it yet.
5. The poster PDF is at `/tmp/Oughton_Avilash_Angirekula_2026ASSIP_Poster.pdf` and `~/datacenter-dataset/figures/Oughton_Avilash_Angirekula_2026ASSIP_Poster.pdf`.
6. **The in-person poster session is 2026-08-12.** That is the next hard date.
7. His mentor is **Prof. Edward J. Oughton**. **Dennies Bor** is a lab member who supplied hazard-layer pointers. Both are listed as co-authors.
8. **The single most important behavioural instruction:** Avi has repeatedly and emphatically asked for adversarial multi-agent verification of all work, and for you to disagree with him and flag problems rather than reassure. Over this project, verification rounds found **false claims on the poster four separate times**, several of which were introduced by the *previous* round's fixes. Never say something is verified unless you just verified it against the data.
9. Avi works from a Mac. He sometimes wants to work from his phone, which is why this handoff file exists.

---

## 1. PROJECT IDENTITY

**What it is:** A reproducible Python data pipeline that (a) compiles an open, building-level geospatial dataset of data centers in the contiguous United States from public sources, and (b) samples official natural-hazard layers at each facility to measure exposure.

**Why it exists:** AI and cloud computing have concentrated enormous computing capacity into a small number of US locations. Those buildings face earthquakes, wildfire and flooding. No open dataset records where they physically stand at building level with verified coordinates. Commercial directories (e.g. Baxtel) are proprietary; open sources are unverified or aggregated above building level. Without building-level locations, nobody can measure what US computing infrastructure is exposed to.

**Who it's for:** Immediately, the ASSIP poster session and Prof. Oughton's GeoAI lab. Longer term, it is intended to feed a multi-hazard risk-assessment paper.

**Stage:** Dataset complete and validated. Hazard exposure complete. Poster complete. The "risk" step (vulnerability/fragility curves that turn exposure into estimated loss) is **not started** and is blocked on the lab.

**Formal project title assigned by the lab** (from Prof. Oughton's 2026-04-01 work-plan email):
> "Data center data collection and then multi-hazard assessment for CONUS"
Advisors listed: Dennies / Ali / Ed. Affiliated grant: **NCAR multi-hazards**. Note that **Aaron Zhile Lin** was assigned the identical topic in that same table.

---

## 2. GOALS & SUCCESS CRITERIA

### Hard requirements (deadlines and stakes)
| Item | Deadline | Status |
|---|---|---|
| Abstract to ASSIP (Canvas) | 2026-07-31, 5 PM | **SUBMITTED** (without mentor sign-off — see §5) |
| Poster to mentor for review | 2026-08-04, 12:00 noon | Draft email prepared; Avi to send |
| Poster to Canvas as PDF | 2026-08-04, 5:00 PM | PDF ready |
| Check Speaking Slot Assignments spreadsheet, report conflicts | 2026-08-04, COB | **NOT CONFIRMED DONE** |
| In-person poster session | 2026-08-12 | Upcoming |

### What "good" means here
- Every number on the poster must be recomputable from `data/processed/`.
- No claim may overstate what the analysis supports.
- The poster must use the official ASSIP template unmodified in its fixed elements (36 × 27 in size, colour scheme, heading bars, logos).
- Avi's stated bar: *"literally backable to be published in a top research paper."*

### Nice-to-haves (not blocking)
- Getting the word count under ~600 (currently 837; this is a target Claude invented, not a program rule).
- Adding the 200 m → 800 m search-widening sensitivity to the poster (it is in the email to Ed instead).

---

## 3. CURRENT STATE (as of 2026-08-04 ~14:30)

- **Dataset:** DONE. 2,696 facilities, contiguous US.
- **Hazard exposure:** DONE. Seismic, wildfire, flood, lightning, water stress, storms (tornado/hail/wind/tropical cyclone).
- **Validation work:** DONE. Seismic external validation, soil sensitivity, storm reporting-bias diagnostic, positional-error Monte Carlo, footprint-vs-point comparison, building-height control.
- **Poster:** DONE and exported to PDF. Passed all automated layout checks. All 19 spot-checked numbers verified against the data.
- **Email to Ed and Dennies:** Gmail draft exists (draft ID `r-2161842325499685495`), fully written, **not sent**. Avi must attach the PDF manually before sending.
- **Tests:** 94 passing. **Lint:** ruff clean across `scripts/`, `src/`, `tests/`.
- **Git:** 59 commits, all pushed to `origin/main`.

---

## 4. DONE / IN PROGRESS / NOT STARTED

### DONE
| Work | Where it lives | State |
|---|---|---|
| 3-source merge → 2,696 CONUS facilities | `data/processed/datacenters_final.csv` | Final |
| Entity resolution / deduplication, 194 merges | `src/dcdata/resolve/dedup.py`, `data/processed/merge_log.json` | Final; every merge logged with distance + name-similarity evidence |
| Coordinate precision taxonomy | `data/processed/datacenters_final.csv` col `coordinate_precision` | Final |
| Independent verification vs non-OSM footprints | `scripts/independent_verify.py`, col `coordinate_status` | 1,546 independently confirmed on a building |
| Manual/AI-assisted satellite adjudication of 1,150 sites | `data/processed/building_verification_results.csv` | 416 VERIFIED, 550 CANDIDATE, 104 AMBIGUOUS, 80 UNRESOLVABLE |
| FEMA USA Structures building match | `scripts/build_building_attributes.py`, `data/processed/building_attributes.csv` | 1,681 contains / 993 nearest / 22 none |
| Building search widened 200 m → 800 m | same | Cut misses 256 → 22, changed **zero** containment results |
| USGS seismic (authoritative per-facility) | `scripts/fetch_seismic_authoritative.py`, `data/raw/seismic_points_multilevel.jsonl` | Final; replaced a failed contour-sampled layer |
| Seismic external validation | `scripts/validate_seismic.py`, `data/processed/seismic_validation.json` | **Failed**, and that failure drove the replacement |
| Soil site-class sensitivity | `data/processed/seismic_validation.json` → `soil_sensitivity` | B/BC 1.00, C 1.06, D 1.12, E 1.09 |
| USFS wildfire, 3 buffer radii | `scripts/build_hazard_exposure.py`, `src/dcdata/hazards/sample.py` | 1 km → 342, 2.4 km → 646, 5 km → 953 |
| FEMA flood (NFHL layer 28, SFHA) | `scripts/fetch_building_attributes.py` | 71 in SFHA; 72 outside mapped extent |
| Lightning flash density | `data/processed/hazard_exposure.csv` | Computed, not used in the exposure flag |
| WRI Aqueduct 4.0 water stress | `scripts/build_water_stress.py`, `data/processed/water_stress.csv` | 2,696/2,696 matched to a basin |
| Storm exposure (tornado/hail/wind/TC) | `scripts/build_storm_exposure.py`, `data/processed/storm_exposure.csv` | Exact Poisson CIs; excluded from poster results |
| Storm reporting-bias diagnostic | `scripts/storm_bias_diagnostic.py`, `data/processed/storm_bias_diagnostic.json` | Drove the decision to exclude hail and wind |
| 500-draw positional-error Monte Carlo | `scripts/coordinate_uncertainty.py` | Covers **wildfire and lightning only** |
| Footprint vs point hazard sampling | `scripts/build_footprint_hazard.py`, `data/processed/footprint_vs_point.json` | 29 of 326 comparable sites differ |
| Building height / storey control | `data/processed/footprint_vs_point.json` → `storey_control` | Null once state is held constant |
| ASSIP poster | `figures/Oughton_Avilash_Angirekula_2026ASSIP_Poster.pptx` and `.pdf` | Final, exported |
| Poster figures | `figures/poster/fig1_map.png`, `fig2_states.png`, `fig3_confidence.png` | Final |
| Automated poster layout checker | `scripts/check_poster.py` | Passing (one soft word-count warning) |
| Human-verifiable spot check tool | `scripts/spot_check.py` | Prints facilities with links to Google Maps / USGS / FEMA so a human can check independently |
| Abstract | Google Doc `1ecBE0B5rHNgCTjwQ-8kCkmcetICh0JM_mauuJZcraaE` | Submitted 2026-07-31; **now out of date vs the poster** |

### IN PROGRESS / LEFT OFF AT
- **Gmail draft to Ed + Dennies.** Draft ID `r-2161842325499685495`. Fully written. **Next physical action: attach `/tmp/Oughton_Avilash_Angirekula_2026ASSIP_Poster.pdf` and press send.**
- **Canvas submission.** PDF ready, not confirmed uploaded.
- **Speaking Slot Assignments spreadsheet.** Not confirmed checked. Link in Amanda Haymond Still's 2026-08-03 email (SharePoint).

### NOT STARTED
- **Vulnerability / fragility curves** — the actual risk step. Blocked on the lab.
- **Landslide hazard layer** — could not be obtained (see §15).
- **Licence file for the repo** — blocked on a lab decision (OSM ODbL share-alike may constrain the choice).
- **Power capacity (MW)** — null for every record; would require licensing a commercial directory such as Baxtel.
- **Sampling the NSHM grid for 475-year and 975-year seismic levels** — doable without anyone, not done.
- **`run_all.sh` driver script and a pinned dependency lockfile** — reproducibility gaps, doable without anyone.
- **A fetcher for the WRI Aqueduct GDB** — currently `build_water_stress.py` exits if the file is absent, and there is no documented download step.

---

## 5. PEOPLE

### Avilash Angirekula ("Avi") — the user
- High-school student at Thomas Jefferson High School for Science and Technology (TJHSST), Virginia.
- Email: `avilasha153@gmail.com` (personal, used for all ASSIP correspondence). Also `angirekulah@gmail.com` is registered in his Claude account.
- Signs emails **"Much Thanks, Avi"** and opens **"Dear Professor Oughton,"**.
- Accepted the ASSIP position 2026-03-30. Also had an offer from Prof. Ningshi Yao's lab and chose Oughton's.

### Prof. Edward J. Oughton — mentor
- Email: `eoughton@gmu.edu`
- Assistant Professor, Department of Geography and Geoinformation Sciences, College of Science, George Mason University.
- Runs a weekly "GeoAI and Earth Observation" research meeting (Fridays 11am, GGS, Exploratory Hall).
- **Note:** Avi has referred to him verbally as "Edward Odin" — that is a mis-transcription; the correct name is **Oughton**.
- Tone: brief, warm, practical. Examples: *"Hi Avi, This sounds great and very good progress."* / *"Hi Folks, ... Please keep up your side of the bargain."*
- **What he asked for specifically:** (a) once the dataset was validated, ask Dennies for multi-hazard layers and start intersecting building footprints; (b) a building-height / storey control (this was done and came back null).
- **He is a co-author on the poster and abstract.**
- **He never signed off on the abstract.** The abstract Google Doc has a "Mentor Acknowledgement" section requiring him to comment "I agree" — there is no such comment. Avi submitted it anyway after waiting ~4 hours, and told Ed so.
- His 2026-08-03 email said: *"you need to submit your poster to your mentor for review by noon tomorrow... You basically need it signed off by us before you submit it."*

### Dennies Bor — lab member / collaborator
- Email: `dbor@gmu.edu`
- Pointed Avi to the multi-hazard datasets via `https://github.com/denniesbor/mhtran/tree/main` (Zenodo links in that repo).
- **He is a co-author on the poster and abstract.**
- **IMPORTANT CORRECTION made during this project:** Dennies Bor is **NOT** an author of the Zenodo multi-hazard transmission-network record. That record's authors are **Oughton, E. J., & Weigel, R.** An earlier draft credited Bor and this was wrong. It is now cited correctly on the poster.

### Amanda Haymond Still — ASSIP program director
- Email: `cosassip@gmu.edu`
- Runs the program logistics, deadlines, poster templates, speaking-slot assignments.
- Authored the seminar deck `5. How to create figures and a poster.pdf`, which is the authority on poster design for this program (36 pages).
- Her 2026-08-03 email set the poster deadline and asked for conflicts on the Speaking Slot spreadsheet by COB 2026-08-04.

### Others (lower relevance)
- **Aaron Zhile Lin** — ASSIP student assigned the *same* project topic in the April work plan. Unclear whether he is doing overlapping work.
- **Ali Kothawala** (`akothaw@gmu.edu`) — listed as an advisor on this project in the work plan.
- **Alice Fox** (`afox30@gmu.edu`) — ran an "ASSIP Project Virginia Context" check-in.
- **Jim Gallagher** (`jgalla5@gmu.edu`), **Dante Groccia** (`dgroccia@gmu.edu`) — other lab staff on cc lists.

### What Avi owes / is owed
- **Owes:** poster to Ed and Dennies for sign-off; Canvas upload; speaking-slot conflict check.
- **Owed:** Ed's sign-off on the poster; Ed's "I agree" on the abstract (never given); lab decisions on vulnerability curves, licence, power-capacity licensing, and a landslide source.

---

## 6. DECISIONS & RATIONALE

These are settled. **Do not re-litigate or silently reverse them.**

| Decision | Chosen | Why | Rejected alternative |
|---|---|---|---|
| Exposure, not risk | Report *exposure* (is a site in a hazard zone) | No vulnerability term exists yet | Calling it "risk", which would be unsupportable |
| Wildfire measured in a buffer, not at the point | Max WHP class within **2.4 km** | 2,284 of 2,696 sites sit on land WHP classes as **non-burnable**, so the pixel under the building carries no information | Point sampling (useless here) |
| Which buffer radius to headline | 2.4 km (middle of 1 / 2.4 / 5 km tested) | Reported with its sensitivity so the reader sees what the choice is worth | Earlier the abstract used 5 km |
| Seismic source | USGS ASCE 7-22 Design Maps **web service**, per facility | The original contour-sampled layer failed validation: only 22 of 150 test sites within 10%, median bias +32% | The contour shapefile (Petersen 2023, doi:10.5066/P9GNPCOD) — **discarded** |
| Hail and wind excluded | Excluded from every result | Within-state Spearman 0.39 and 0.34 against local facility density, i.e. they measure observer density | Including them with a caveat |
| Tornado, lightning, tropical cyclone | Computed, **not** folded into the exposure flag | Same reporting-bias family / not building-scale | Silently omitting them (now disclosed on the poster) |
| Water stress | Reported **separately**, never combined into a hazard index | It is a resource/supply constraint, not a natural hazard | Adding it to `n_haz` |
| Missing hazard values | Recorded as unknown in the tables; the exposure flag counts them not-exposed, and the poster says **"35% is a floor"** | Honest disclosure beats a false precision | Claiming unknown is never treated as zero (this was on the poster and was **false** — corrected) |
| Poster built by editing the official template | `build_poster.py` opens the shipped `.pptx` and replaces placeholder text only | An earlier version cleared the template and rebuilt a lookalike; Avi caught it | Rebuilding the layout from scratch |
| Poster title | **"A Multi-Hazard Assessment of 2,696 US Data Centers"** | Closest to the lab-assigned project topic; no jargon; fits one line at 78 pt | (a) "Two Americas of Data Center Hazard" — rejected, loaded US political idiom; (b) matching the abstract title verbatim — rejected, 24 words and describes an analysis the poster no longer leads with |
| Repo URL on the poster | **Removed** at Avi's explicit request | His call | Keeping it in Acknowledgements |
| Figure 2 design | **Facility-weighted histogram**, stacked by dominant hazard | Height means facilities; nothing can occlude anything; shows bimodality rather than asserting it | (a) top-7/bottom-7 bar chart — rejected, deleted Texas and 43% of the fleet; (b) dot plot / beeswarm — rejected twice, vertical position encoded nothing but looked like it did |
| Colour palette | Okabe-Ito, colourblind-safe | Fig 1 uses grey/blue/vermillion for hazard **count**; Fig 2 uses grey/orange/teal/purple for hazard **type**, deliberately non-overlapping with Fig 1 | An earlier version reused the same blue and vermillion across figures with different meanings |
| Do not add Claude as a git co-author | Standing rule | Avi's instruction; was removed from history previously | — |

---

## 7. CONSTRAINTS

**Poster (from the ASSIP template and Amanda Haymond Still's seminar deck):**
- Size **36 × 27 inches** — cannot be changed.
- Colour scheme (GMU green `#006600`, gold `#FFCC00`) — cannot be changed.
- Template body text is **26 pt**; the deck says "I wouldn't go much smaller" and "stay at font size 20+ for legibility".
- Images should be **300 DPI** at placed size.
- Headings, logos and box geometry ship with the template and were preserved.
- The deck explicitly warns about AI-generated figures and content: *"having AI make your figures also cedes a lot of storytelling to an AI that you ought to retain yourself."*
- Acknowledgements should thank people **not already on the author list**.

**Template file:** `/Users/avilash/Downloads/MentorLastName_FirstName_LastName_2026ASSIP_Poster.pptx` (also copied to `/tmp/assip_template.pptx`, which `build_poster.py` reads).
**Guidance deck:** `/Users/avilash/Downloads/5. How to create figures and a poster.pdf`

**Filename convention:** `MentorLastName_FirstName_LastName_2026ASSIP_Poster` → `Oughton_Avilash_Angirekula_2026ASSIP_Poster.pdf`

**Data/legal:**
- 1,530 of 2,696 records derive from **OpenStreetMap (ODbL, share-alike)**, which may constrain the dataset licence. No LICENSE file exists yet.
- Baxtel and other commercial directories forbid scraping in their ToS; documented in `docs/TIER2_TOS_REPORT.md`.

**Writing style (Avi's standing rules):**
- **No em dashes.**
- **No semicolons.**

---

## 8. AVI'S PREFERENCES & WORKING STYLE

Direct quotes and things he has corrected:

- *"I want every time you do the work, test agents criticizing your work to ensure that everything you do is literally perfect."*
- *"always with the multiple agents verify and ensuring top quality and critiquing and constantly fixing your work"*
- *"be honest with me, don't disagree with me. Please always be willing to disagree with me and question me... don't be afraid to critique me or tell me I need to fix something."* (The "don't disagree" is a slip; the clear intent is **do** push back.)
- *"I don't wanna just be able to saying this and then have it in reality be that none of this works."* — he wants verification he can trust, not assurances.
- He asked for a **personal voice**, *"like my voice so its not js complete ai"* — this applies to the abstract and poster prose.
- He asks for **concision** in progress updates: *"for the progress please be a lot more concise js paste the updated email here ill copy it"*.
- He pushed back hard when told something was done and it wasn't: *"every time I tell you to check something, you constantly find an error. So I don't even know if this is good now."*
- He catches visual problems by **looking at rendered images**, and has twice found real defects that automated checks and four review agents all missed.
- He does not want Claude added as a git co-author.
- He types quickly and informally ("js" = "just", "ab" = "about", "u" = "you", "smth" = "something"). Read past the typos.

**Output style that works for him:** short, scannable, tables over paragraphs, exact numbers, a clear recommendation rather than a menu of options, and an explicit statement of what is *not* verified.

---

## 9. DOMAIN CONTEXT & TERMINOLOGY

| Term | Meaning as used here |
|---|---|
| **CONUS** | Contiguous United States (lower 48). 15 facilities in AK/HI/PR were excluded; they live in `data/processed/datacenters_non_conus.csv` |
| **Exposure** | Whether a facility lies inside a hazard zone. **Not** damage, loss, or risk |
| **Risk** | Exposure × vulnerability × consequence. This project stops at exposure |
| **WHP** | USFS **Wildfire Hazard Potential**, a 270 m raster. Classes 1–5 are an ordinal severity ladder. **Class 6 = non-burnable** (developed, agriculture, barren, rock), **class 7 = water**. 6 and 7 are *nominal* and must never be treated as "higher than 5" |
| **SFHA** | FEMA **Special Flood Hazard Area** — the regulatory 1%-annual-chance ("100-year") floodplain |
| **NFHL** | FEMA **National Flood Hazard Layer**. Layer 28 of the MapServer is the one queried |
| **PGA** | Peak Ground Acceleration, in units of g |
| **MCE_G / MCE_R** | Maximum Considered Earthquake ground motion. MCE_R is *risk-targeted*. **Careful:** the repo's own validation file describes the sampled column as *uniform-hazard 2% in 50 yr, NOT risk-targeted*, so the poster deliberately avoids the term "MCE_G" and says "peak ground acceleration, 2% chance in 50 years" |
| **ASCE 7-22** | The building-design standard whose seismic values the USGS Design Maps web service returns |
| **Site class BC** | The reference rock/firm-soil site condition used for all seismic queries |
| **Aqueduct 4.0** | WRI's water-risk atlas. "Baseline water stress" = withdrawals / available supply, computed **per river basin**, not per building |
| **EPSG:4326** | WGS84 lat/lon (geographic). All facility coordinates are stored in this |
| **EPSG:5070** | NAD83 Albers Equal Area CONUS, in metres. Used for **wildfire buffers** and distance work |
| **IBTrACS** | NOAA's International Best Track Archive for Climate Stewardship. North Atlantic subset used for tropical cyclones |
| **SPC** | NOAA Storm Prediction Center. Source of tornado/hail/wind reports, 2000–2024 window |
| **PeeringDB** | An open database of network interconnection facilities. Contributed 1,158 records |
| **ODbL** | Open Database License, OpenStreetMap's share-alike licence |
| **ASSIP** | Aspiring Scientists Summer Internship Program, GMU College of Science |

**Method notes worth knowing:**
- Buffer statistics are **area-weighted** over the cells the buffer touches. An earlier unweighted version inflated a result from 8.9% to 12.3% and was corrected.
- Storm counts use **event-days**, not raw reports, with **exact (Garwood) Poisson 95% intervals** via `scipy.stats.chi2`.
- The positional-error Monte Carlo uses **500 draws**, fixed seed **20260731**, isotropic Gaussian, sigma assigned per coordinate-precision tier (10 / 30 / 100 / 250 / 500 m), with a cos(latitude) correction converting metres to degrees.

---

## 10. RESEARCH, SOURCES & KEY FINDINGS

### Data sources actually used
| Layer | Source | Access |
|---|---|---|
| Facilities | OpenStreetMap (1,530), PeeringDB (1,158), Wikidata (8) | APIs, cached in `data/raw/` |
| Building footprints | **FEMA / ORNL USA Structures** | ArcGIS REST `services2.arcgis.com/.../USA_Structures_View/FeatureServer/0` |
| Flood | FEMA National Flood Hazard Layer, **layer 28**, field `SFHA_TF` | `hazards.fema.gov/.../NFHL/MapServer/28/query`, `inSR=4326` |
| Seismic | USGS ASCE 7-22 Design Maps web service | `earthquake.usgs.gov/ws/designmaps/asce7-22.json`, site class BC |
| Wildfire | USFS Wildfire Hazard Potential 2023, 270 m, `whp2023_cls_conus.tif` | doi:10.2737/RDS-2015-0047-4 |
| Water stress | WRI Aqueduct 4.0 baseline annual, `bws_cat` | GDB, **no fetcher in the repo** |
| Storms | NOAA SPC SVRGIS 2000–2024; IBTrACS North Atlantic 1980–2024 | Shapefiles in `data/hazards/` |
| Lightning | LIS/OTD climatology, `lightning_annual_rate_4326.tif`, ~0.5° grid | raster |
| Geography | US Census TIGER county shapefile `tl_2024_us_county.shp` | for the Fig 1 basemap |

### Prior art / related
- **Oughton, E. J., & Weigel, R. (2026)** *A Comparative Multi-Hazard Risk Assessment of the US High-Voltage Transmission Network.* Zenodo, doi:10.5281/zenodo.20331026, CC BY 4.0. This is the mentor's own framework applied to transmission; it is cited on the poster. **Dennies Bor is not an author of it.**
- **arXiv 2411.09786** — has coordinates, sqft and MW for ~1,182 US facilities but the dataset is not open ("available via collaboration with authors", Harvard NSAPH) and is derived from Baxtel. Noted in `docs/TIER2_TOS_REPORT.md`.
- **Baxtel** — richest commercial directory, "8,000+ facilities across 600 regions" (that figure is **global**, not US). ToS forbids scraping but they sell a licence.

### Findings flagged as unverified or needing a check
- The "1.5 mile ember-cast distance" justification for the 2.4 km buffer was **asserted without a source and removed**. The repo justifies *buffering* (ember cast from surroundings) but never the specific distance.
- The 475-year and 975-year seismic levels remain **approximate** — they were contour-sampled and there is no public point service for them.
- Lightning is a ~50 km grid, so it is regional, not building-scale.
- Storm exposure is a **regional areal density**, not a site-specific strike rate (except the tornado path-area column).
- 8 facilities sample on an open-water pixel, flagged `qa_coordinate_on_water`.

---

## 11. TECHNICAL DETAILS

### Environment
- **Python 3.13.5**, virtualenv at `~/datacenter-dataset/.venv`. Always invoke as `./.venv/bin/python`.
- Key packages (from `requirements.txt`, all `>=` pins, **no lockfile**): `pandas>=2.2`, `geopandas>=1.0`, `shapely>=2.0`, `rasterio>=1.3`, `scipy>=1.11`, `pyogrio>=0.7`. Also `python-pptx`, `matplotlib`, `Pillow`, `rapidfuzz`.
- Verified working versions recorded in `docs/PROJECT_STATE.md`: pandas 3.0.3, geopandas 1.1.3, shapely 2.1.2, pyproj 3.7.2, rasterio 1.5.0, scipy 1.18.0, pyogrio 0.12.1, GDAL 3.12.1, PROJ 9.5.1.
- Lint: `ruff`. Tests: `pytest`, **94 passing**.

### Repo layout
```
~/datacenter-dataset/
├── README.md, SOURCES.md, requirements.txt, pyproject.toml
├── config/            settings.yaml, sources.yaml
├── src/dcdata/        library code
│   ├── hazards/sample.py     raster/polygon sampling primitives
│   └── resolve/dedup.py      entity resolution
├── scripts/           22 runnable scripts (see below)
├── data/
│   ├── raw/           source API caches, seismic_points_multilevel.jsonl
│   ├── hazards/       downloaded rasters and shapefiles
│   └── processed/     31 output files (CSV / JSON / GPKG)
├── docs/              6 markdown docs
├── figures/           poster + figures
└── tests/             94 tests
```

### Key scripts
| Script | Does |
|---|---|
| `fetch_hazard_data.py` | Downloads hazard layers. Carries URL, byte size, MD5, DOI, licence per layer, with a `--verify` mode |
| `build_hazard_exposure.py` | Main hazard builder: seismic, lightning, wildfire buffers; merges the authoritative seismic |
| `fetch_seismic_authoritative.py` | Per-facility USGS ASCE 7-22 queries (pgam, ss, s1, BSE-2E, BSE-1E) |
| `validate_seismic.py` | External validation of the seismic layer. **This is the one that failed** |
| `build_building_attributes.py` | USA Structures matching, heights, FEMA flood join |
| `independent_verify.py` | Cross-checks coordinates against non-OSM footprint sources |
| `build_footprint_hazard.py` | Area-weighted zonal stats across whole building footprints; the storey control |
| `build_storm_exposure.py` | SPC + IBTrACS, event-days, exact Poisson CIs, Thom/Schaefer path-area estimator |
| `storm_bias_diagnostic.py` | Quantifies observer-density bias in storm reports |
| `build_water_stress.py` | WRI Aqueduct basin join |
| `coordinate_uncertainty.py` | 500-draw Monte Carlo. **Needs `PYTHONPATH=src`** unlike the others |
| `make_poster_figures.py` | Builds the three poster figures |
| `build_poster.py` | Fills in the official template |
| `check_poster.py` | Automated layout verification + schematic preview |
| `spot_check.py` | Prints facilities with public links so a human can verify independently |

### `build_poster.py` — how it works (important for anyone editing the poster)
- Reads the template from the hardcoded path **`/tmp/assip_template.pptx`**. If that file is missing, copy it from `~/Downloads/MentorLastName_FirstName_LastName_2026ASSIP_Poster.pptx`.
- It **edits the template in place**: finds each shape by the first words of its placeholder text, replaces the text, and resizes the box.
- Template geometry (fixed, read back from the shipped file):
  - col 1 `x=0.41 w=11.25` — Background at `y=5.74`, Materials and Methods bar at `y=15.72`, body at `y=16.63`
  - col 2 `x=11.99 w=11.79` — Results, one tall box at `y=5.74`
  - col 3 `x=24.16 w=11.37` — Conclusions `y=5.74`, Major Citations bar `y=16.81`, Citations `y=17.74`, Acknowledgements bar `y=22.68`, Ack body `y=23.66`
  - Content bottom is **26.54 in**
- `fit_height()` measures text with **real Arial glyph metrics** via PIL, using an Arial line box factor of **1.15**, and subtracts the hanging indent for bulleted paragraphs. Autofit is deliberately off, so an undersized box **clips** text rather than shrinking it.
- `set_text()` forces **left alignment** — the template ships `JUSTIFY`, which stretches word gaps — and normalises text-frame margins to 0.10 in (the template ships 0.18 in).
- Template text-frame insets are **0.18 in**; `fit_height` assumes 0.10 in, so `set_text` overrides them. Getting this wrong clipped the Methods paragraph once.

### `make_poster_figures.py` — the figure export trap
- `DPI = 340`.
- **`save_at(fig, name, placed_w_in)`** saves with `bbox_inches="tight", pad_inches=0.14` and then **resamples the PNG to exactly `DPI * placed_w_in` pixels**. This is essential: `bbox_inches="tight"` trims to the ink, so without the resample each figure lands at a different scale on the sheet and a nominal 19 pt label prints at 16.9 / 18.3 / 21.2 pt depending on the figure. With the resample the scale is exactly 1.0 and nominal pt = printed pt.
- **Do not remove `bbox_inches="tight"`.** It was tried; it clips every title and legend drawn outside the axes.
- **Do not try to fix the font scale by raising nominal sizes.** It does not converge — bigger fonts widen the trimmed bbox, which shrinks the scale again.
- Placed widths: fig1 `11.79`, fig2 `11.79`, fig3 `11.37`.

### Known bugs / things that were tried and failed
- Concurrent hazard fetchers once produced **2,992 duplicate rows** in a 4,963-line append-only cache. Never run two fetchers against the same cache file.
- `build_id` was float in one table and int in another (`16010881.0` vs `16010881`), silently recovering 0 polygons. Fixed with a normaliser.
- Nearest-building matching by **centroid** picked the wrong building for 217 of 728 cases. Fixed to use edge distance via `shapely.ops.nearest_points`.
- Polygon parsing that read only `rings[0]` produced a 44.65% area error. Fixed to parse all rings including holes and multipart.
- The buffer disc was once centred on the array-index centre rather than the facility. The first regression test **passed under the bug** because the defect cancels at some sub-pixel alignments; it took a parametrized sweep of sub-pixel offsets to catch.
- Ruff suggested rewriting `flood_sfha == True` as a truthiness check. **This was refused and must stay** — `NaN` is truthy, so the rewrite would count failed verifications as successes. It carries `# noqa: E712`.

---

## 12. BUSINESS / STARTUP DETAILS

Not applicable. This is academic research.

---

## 13. ARTIFACTS & DELIVERABLES

| Artifact | Path | Status |
|---|---|---|
| Poster (PowerPoint) | `~/datacenter-dataset/figures/Oughton_Avilash_Angirekula_2026ASSIP_Poster.pptx` | Final |
| Poster (PDF, submission copy) | `/tmp/Oughton_Avilash_Angirekula_2026ASSIP_Poster.pdf` **and** `~/datacenter-dataset/figures/Oughton_Avilash_Angirekula_2026ASSIP_Poster.pdf` | Final. 36×27 in, 1 page, ~1.3 MB, 14 embedded Arial subsets. **`/tmp` is cleared on reboot — the repo copy is durable** |
| Figure 1 (map) | `figures/poster/fig1_map.png` | Final, 340 DPI |
| Figure 2 (histogram) | `figures/poster/fig2_states.png` | Final, 340 DPI |
| Figure 3 (uncertainty) | `figures/poster/fig3_confidence.png` | Final, 340 DPI |
| Layout preview | `figures/poster_preview.png` | Schematic, generated by `check_poster.py` |
| Abstract | Google Doc ID `1ecBE0B5rHNgCTjwQ-8kCkmcetICh0JM_mauuJZcraaE` | Submitted 2026-07-31, **out of date** |
| Email draft to Ed + Dennies | Gmail draft ID `r-2161842325499685495` | Written, **not sent**, needs PDF attached |
| Official template | `~/Downloads/MentorLastName_FirstName_LastName_2026ASSIP_Poster.pptx`, copy at `/tmp/assip_template.pptx` | Unmodified |
| Poster guidance deck | `~/Downloads/5. How to create figures and a poster.pdf` | Reference, 36 pages |
| Project state doc | `docs/PROJECT_STATE.md` | Living handoff doc in the repo |
| Hazard methodology | `docs/hazard_exposure.md` | Detailed method + limitations |
| Data dictionary | `docs/data_dictionary.md` | Column-by-column |
| ToS/licensing report | `docs/TIER2_TOS_REPORT.md` | Commercial directory analysis |

---

## 14. CONTENT PRODUCED SO FAR (verbatim)

### 14a. The poster — every word currently on it

**TITLE**
> A Multi-Hazard Assessment of 2,696 US Data Centers

**AUTHORS**
> Avilash Angirekula¹, Dennies Bor¹, Edward J. Oughton¹

**AFFILIATION**
> ¹Department of Geography and Geoinformation Sciences, College of Science, George Mason University

**BACKGROUND** (bulleted, 26 pt)
> •  AI and cloud demand has concentrated US computing into a few dozen metro clusters that face earthquakes, wildfire and flooding.
> •  Existing sources are proprietary, or give city-level coordinates never checked against a building.
> •  We built a free, public, building-level inventory of the contiguous US, and tested how much the answer moves when a coordinate is wrong.
> •  We measured exposure, meaning whether a site lies in a hazard zone. We did not model damage, so nothing here is a loss estimate.

**LIMITATIONS** (grey panel with gold accent bar, 22 pt, heading bold)
> Limitations
> •  Coverage is uneven. 83% of our Virginia sites come from OpenStreetMap against 48% of our California ones, so part of the gap between states reflects who did the mapping.
> •  Hail and wind come from eyewitness reports, so within a state their rates track the number of other sites within 40 km (Spearman 0.39 and 0.34). We left both out, along with lightning, tornado and hurricane.
> •  No public source lists power capacity, so a server room counts the same as a 100 MW campus.
> •  40 sites shown as clear sit outside FEMA's mapped extent and 8 outside the wildfire raster, so 35% is a floor.

**MATERIALS AND METHODS** (26 pt)
> We merged OpenStreetMap, PeeringDB and Wikidata into one record per site across the contiguous US, matching on name and distance, with written evidence kept for all 194 merges.
> Against FEMA USA Structures footprints, 1,681 coordinates fall inside a building, 993 match the nearest and 22 have no match. A second non-OSM source confirmed 1,546, and we re-checked the 1,150 least certain with an AI-assisted pipeline we then reviewed.
> Our first seismic layer failed validation against USGS reference values (22 of 150 sites within 10%), so we replaced it:

**METHODS TABLE** (5 rows, grey panels, 22 pt / 21 pt)
| Earthquake | USGS ASCE 7-22 shaking, 2% chance in 50 yr |
| Wildfire | USFS Hazard Potential 270 m, max in 2.4 km |
| Flood | FEMA flood layer, 1-in-100-year floodplain |
| Water stress | WRI Aqueduct 4.0, river-basin scale |
| Uncertainty | 500 relocations per site, 10-500 m by precision |

**METHODS TAIL** (26 pt)
> A site counts as exposed if it lies within 2.4 km of land rated High or Very High for wildfire, inside a FEMA Special Flood Hazard Area, or at peak ground acceleration of 0.30 g or above. Wildfire is buffered because 2,284 sites sit on non-burnable land, where the pixel under the building says nothing.

**RESULTS — headline statistic tiles** (48 pt green numbers, 20 pt grey labels)
| 2,696 | facilities located |
| 954 | face a mapped hazard |
| 952 | in a high water-stress basin |
| 563 | water-stressed only |

**RESULTS LEAD** (29 pt bold)
> Hazard and water stress pick out largely different buildings. Counting both raises the share under a physical constraint from 35% to 56%.

**RESULTS BODY** (26 pt)
> 952 sites lie in a high or extremely-high water-stress basin, almost exactly the 954 facing a mapped hazard, but only 389 are the same sites. Some of the largest clusters are stressed while their hazard maps read clear: Virginia is 0.7% hazard-exposed and 31% water-stressed, Illinois 2.7% and 95%.
> Which hazard dominates depends on the region. New Jersey reaches 100% through wildfire alone and 0% through earthquake, California 96% earthquake. Nationally 646 sites are exposed to wildfire, 448 to earthquake and 71 to flood.
> Widening the wildfire buffer from 2.4 km to 5 km takes the wildfire count from 646 to 953, so that result is a statement about the buffer as much as about the site.

**CONCLUSIONS** (bulleted, 26 pt)
> •  A single national rate is close to meaningless. Only 7 of 32 states with 20 or more sites fall between 10% and 60% exposed.
> •  We did not measure any site's water use, but the basins under the largest clusters are already over-drawn, and a hazard screen misses them.
> •  New Jersey and California are both 100% exposed for opposite reasons, so one score hides what a site faces.
> •  Next: fragility curves, to turn exposure into loss.

**ROBUSTNESS PANEL** (grey panel with gold accent, 22 pt, heading bold)
> Two robustness checks
> Sampling across a whole footprint instead of its centre changed the answer for 29 of 326 comparable sites. Taller buildings looked more exposed nationally, but that vanished within states.

**FIGURE CAPTIONS** (22 pt bold)
> Fig 1. One third of US data centers face a mapped hazard. Of the 205 facing two or more (orange), California holds 119, with smaller clusters in Utah, Nevada and New Jersey.
> Fig 2. The fleet piles up at both ends. Colour shows which hazard drives each state.
> Fig 3. Wildfire class under coordinate error.

**MAJOR CITATIONS** (20 pt)
> Dillon, G.K. (2023) Wildfire Hazard Potential for the United States, 270-m, v2023. USDA Forest Service. doi:10.2737/RDS-2015-0047-4
> USGS (2026) ASCE 7-22 Seismic Design Maps web service. earthquake.usgs.gov/ws/designmaps
> FEMA (2026) National Flood Hazard Layer. hazards.fema.gov
> Oughton, E.J. and Weigel, R. (2026) A Comparative Multi-Hazard Risk Assessment of the US High-Voltage Transmission Network. Zenodo. doi:10.5281/zenodo.20331026 (CC BY 4.0)
> FEMA and ORNL (2024) USA Structures. gis.fema.gov
> WRI (2023) Aqueduct 4.0 Water Risk Atlas.

**ACKNOWLEDGEMENTS** (20 pt)
> This research was made possible through the support of George Mason University's College of Science, which supports the ASSIP Program, and by the NCAR multi-hazards project.

**Poster stats:** 63 shapes, 837 words, smallest type 20 pt, 36 × 27 in.

### 14b. The email draft to Ed and Dennies (final, unsent)

**To:** eoughton@gmu.edu, dbor@gmu.edu
**Subject:** ASSIP poster for review, Avilash Angirekula

> Dear Professor Oughton and Dennies,
>
> My ASSIP poster is attached for your review ahead of the 5pm Canvas deadline. Here is everything I have added since the dataset was compiled.
>
> Coordinates. Matched all 2,696 against FEMA USA Structures footprints: 1,681 fall inside a building, 993 match the nearest within 800 m, 22 have no match. A second, non-OSM footprint source independently confirmed 1,546 of them. I re-checked a further 1,150 with AI-assisted checks against web sources and satellite imagery, 15 of them manually. Widening the search from 200 m to 800 m cut misses from 256 to 22 and changed no containment result.
>
> Hazards. USGS seismic ground motion at four hazard levels, USFS wildfire at three buffer radii, FEMA flood zones, lightning flash density, WRI Aqueduct water stress, and tornado, hail, wind and North Atlantic tropical cyclone rates with exact Poisson confidence intervals.
>
> Validation. The seismic layer failed validation against the USGS point service, with only 22 of 150 test sites within 10% and a median bias of +32%, so I replaced it with per-facility authoritative queries. I measured soil site-class sensitivity, which showed reference rock understates soft-soil motion by about 12%. I quantified the storm reporting bias that led me to exclude hail and wind, ran a 500-draw positional-error Monte Carlo on the wildfire and lightning sampling, compared footprint against point sampling, and ran the building-height control you asked for, which came back null once state is held constant.
>
> Results. 954 sites (35%) face at least one mapped hazard, and that is a floor because 48 sites fall outside a hazard layer's extent. Separately, 952 sites lie in a high or extremely-high water stress basin, but only 389 are the same sites, so counting water stress takes the fleet from 35% to 56% facing at least one constraint. Some of the largest clusters are stressed while their hazard maps read clear: Virginia is 0.7% hazard-exposed and 31% water-stressed, Illinois 2.7% and 95%.
>
> Of the 32 states holding 20 or more sites, only 7 sit between 10% and 60% exposed. New Jersey reaches 100% through wildfire alone while California is 96% earthquake, so a combined index has to report hazards separately.
>
> I am happy to change anything you want changed. If you can reply before 5pm I will submit straight after your approval.
>
> Much Thanks,
> Avi

### 14c. The submitted abstract (2026-07-31) — NOW OUT OF DATE

**Title as submitted:**
> A building-level dataset of 2,696 United States data centers shows that more than one third lie within five kilometers of high wildfire hazard land

**Authors:** Avilash Angirekula¹, Dennies Bor¹, Edward J. Oughton¹
**Affiliation:** ¹Department of Geography and Geoinformation Sciences, George Mason University, Fairfax, VA

**Abstract text:**
> Artificial intelligence and cloud computing have concentrated computing capacity and electrical load into a small number of United States locations, which leaves critical digital infrastructure exposed to natural hazards and straining regional grids. Assessing that exposure requires knowing where each facility physically sits. Open sources are incomplete and unverified, and commercial directories are proprietary or aggregated above the building level, so no open dataset supports building-level hazard analysis. This study assembled a reproducible, public dataset of 2,696 data centers across the contiguous United States. A Python pipeline merged OpenStreetMap, PeeringDB, and Wikidata records, resolved duplicates, and graded every coordinate against an independent building footprint source and satellite imagery. Official hazard maps then supplied earthquake ground motion, lightning flash density, and wildfire hazard at each location. Virginia alone holds 409 facilities, which is 15 percent of the national total. Independent footprints place 1,546 coordinates on a building, individual review resolved a further 416, however 184 still remain unmatched. Sampling wildfire hazard at the building itself proved to not be very helpful, because 85 percent of facilities occupy land that the hazard map classifies as developed. When measuring across the surrounding area instead, 342 facilities fall within one kilometer of land rated High or Very High, and 953 within five kilometers. That exposure concentrates in Arizona, New Jersey, and New York rather than California, so wildfire risk to digital infrastructure may be underestimated outside of the states that are typically associated with it. Building-level location data of this type is what multi-hazard risk assessment of computing infrastructure has been missing.

**Divergences between the abstract and the current poster (Avi should be aware):**
- Abstract headlines **5 km** wildfire buffer; poster headlines **2.4 km** (but still reports the 5 km figure of 953).
- Abstract does not include flood or water stress; the poster does.
- Abstract says "1,546 ... a further 416 ... 184 unmatched"; the current numbers are **1,681 contains / 993 nearest / 22 none**.
- Abstract says wildfire exposure "concentrates in Arizona, New Jersey, and New York rather than California." Poster says California is 100% exposed — these do not actually contradict (CA's 100% is driven by **seismic** at 95.5%; CA wildfire is 49.8%) but they read as if they do.
- Abstract says 85% of facilities occupy land the hazard map "classifies as developed." The correct WHP class name is **non-burnable**, not developed. The poster was corrected; the abstract still says developed.

---

## 15. OPEN QUESTIONS & BLOCKERS

### Blocked on Ed / Dennies / the lab
1. **Vulnerability (fragility) curves** for server and cooling equipment. This is the actual risk step and cannot proceed without them.
2. **Dataset licence.** 1,530 of 2,696 records derive from OpenStreetMap (ODbL share-alike), so the choice may be constrained. No LICENSE file exists. Also: is the lab happy for the repo to be public? (It currently **is** public.)
3. **Power capacity.** `power_capacity_mw` is null for every record. Nothing can be weighted by facility size. Would require licensing a commercial directory such as Baxtel.
4. **Landslide layer.** Could not be obtained: USGS ScienceBase items time out, the direct download returns 403, and the ArcGIS `US_Landslide_Susceptibility` layer is a cached tile service with no query capability.
5. **Co-authorship.** Ed and Dennies are listed as co-authors on both the abstract and poster, matching what Avi submitted. The email asks them to confirm or ask to be acknowledged instead. **This question was in an earlier draft and Avi asked for it to be removed** — he plans to raise the blockers separately later.
6. **Ed never signed the abstract.** The mentor acknowledgement in the Google Doc has no "I agree" comment.

### Avi said he would decide later
- Whether to raise the four blockers with Ed (he said *"ill email ab that later maybe"*).
- Whether to trim the poster word count from 837 toward 600.
- Whether to add the 200 m → 800 m search-widening sensitivity to the poster (currently only in the email).

### Unknown / needs checking
- Whether Aaron Zhile Lin is doing overlapping work on the same assigned topic.
- Whether Avi actually submitted the poster to Canvas and checked the Speaking Slot spreadsheet.

---

## 16. NEXT STEPS (prioritised)

1. **Send the email to Ed and Dennies.** Open the Gmail draft, **attach `/tmp/Oughton_Avilash_Angirekula_2026ASSIP_Poster.pdf`** (or the copy in `figures/`), send. Reveal it in Finder with `open -R ~/datacenter-dataset/figures/Oughton_Avilash_Angirekula_2026ASSIP_Poster.pdf`.
2. **Upload the PDF to Canvas** before 5:00 PM 2026-08-04.
3. **Check the Speaking Slot Assignments spreadsheet** (link in Amanda Haymond Still's 2026-08-03 email) and email her about any conflict, by COB 2026-08-04.
4. **Prepare the easel talk for 2026-08-12.** See §17 for the questions a judge is most likely to ask.
5. **If the poster needs another pass:** run `./.venv/bin/python scripts/make_poster_figures.py`, then `scripts/build_poster.py`, then `scripts/check_poster.py`, then re-export the PDF from PowerPoint, then re-verify.
6. **Reproducibility gaps that need no one else:** commit a `pip freeze` lockfile; write a `run_all.sh` listing the pipeline commands in order; add an Aqueduct GDB fetcher to `fetch_hazard_data.py`; add `make_poster_figures.py` and `build_poster.py` to the documented run list; replace the hardcoded `/tmp/assip_template.pptx` path.
7. **Analysis that needs no one else:** sample the NSHM grid for the 475-year and 975-year seismic levels to replace the approximate contour-sampled values.
8. **Eventually:** raise the four blockers with Ed and Dennies.

### How to re-export the PDF (macOS, PowerPoint)
```bash
cd ~/datacenter-dataset
osascript -e 'tell application "Microsoft PowerPoint" to close every presentation saving no'
rm -f "figures/~\$Oughton_Avilash_Angirekula_2026ASSIP_Poster.pptx"
open -a "Microsoft PowerPoint" figures/Oughton_Avilash_Angirekula_2026ASSIP_Poster.pptx
sleep 9
osascript -e 'tell application "Microsoft PowerPoint" to save active presentation in POSIX file "/tmp/Oughton_Avilash_Angirekula_2026ASSIP_Poster.pdf" as save as PDF'
cp /tmp/Oughton_Avilash_Angirekula_2026ASSIP_Poster.pdf figures/
```
A `~$...pptx` lock file means PowerPoint still has it open — delete it and reopen before exporting, or you will export a stale file.

---

## 17. FAILURE MODES & WATCH-OUTS

### Errors that were actually made on this poster and corrected — do not reintroduce
| Wrong claim | Truth |
|---|---|
| "No state sits between 3% and 75%" | **False.** 17 states with 20+ facilities do. The apparent gap was an artefact of plotting only 7 lowest + 7 highest of 32 states |
| "Eighteen states holding half the fleet sit below 10%" | It is **15 states holding 48%** |
| "2,067 facilities never change class" | **1,681** never change. 2,067 is the count changing in under 5% of draws |
| "Missing data is recorded as unknown, never as zero" | **False.** The exposure flag uses `.fillna(False)`; 81 facilities with an unknown hazard are counted not-exposed. 35% is a floor |
| "8.9% of facilities" (footprint vs point) | It is 29 of the **326 comparable** facilities, not 8.9% of all 2,696 |
| "we reviewed 1,150 against satellite imagery by hand" | **False.** 1,135 of 1,150 rows record `verification_method = "AI-assisted verification"`; only 15 were manual |
| "New Jersey ... (the Pine Barrens rate High or Very High)" | **False.** All 91 NJ sites are in North Jersey, latitude 39.83–41.08. Zero are in the Pine Barrens |
| "the threshold moves the answer by half" | 646 → 953 is a **+48% increase**, not a halving |
| Fig 1 "concentrate in California and the Northeast" | The Northeast holds **21 of 205** (10%). California holds 119 |
| "Hail and wind reports rise with population density" | **No population data was used.** The proxy is count of other facilities within 40 km, and 0.39 is the *within-state* figure (raw hail is 0.062) |
| Citing Petersen 2023 (doi:10.5066/P9GNPCOD) | That is the **contour product that failed validation and was discarded.** The poster now cites the ASCE 7-22 web service actually used |
| "MCE_G" as the seismic label | MCE_G/MCE_R are *risk-targeted* terms; the validation file says the sampled quantity is uniform-hazard and **not** risk-targeted. The term was removed |
| "positional uncertainty carried through the hazard sampling" | The Monte Carlo covers **wildfire and lightning only**, not seismic or flood |
| "Building height showed no association" | The unconditioned Mann-Whitney is significant at p=0.025; only the **within-state** difference vanishes |
| "The 2.4 km radius is the 1.5 mile ember-cast distance" | **Invented.** The repo justifies buffering but never sources that specific distance |
| "2,284 sites sit on land the wildfire map classes as developed" | WHP code 6 is **non-burnable**, which also covers agriculture, barren and rock |
| "The hazard map and the water map barely overlap" | **Overstated.** Observed overlap 389 vs 337 expected under independence — it is 15% **above** chance |
| "Water stress lands hardest where the hazard map says clear" | **False and backwards.** 40.8% of hazard-exposed sites are water-stressed vs 32.3% of clear ones. Odds ratio 1.44, p = 1.4e-5 |
| Fig 3 "flips the wildfire class for at most 9% of sites" over 500 draws | 9% is the mean probability of a flip in **one** relocation. Over 500 draws, **52.6%** of the 100 m tier flips at least once |
| "The 35% headline is the least useful number here" | There was no 35% headline once the stat tiles became counts — it attacked a phantom |

### Process failure modes
- **The biggest one:** reporting "verified" after applying fixes, when the verification ran against the *previous* version. Four rounds of review each found errors, and rounds 3 and 4 each found errors introduced by the previous round's fixes. **Always re-verify the artifact you are about to hand over, not the one you reviewed.**
- **Review agents are sometimes wrong.** One claimed "1,681 never changed wildfire class" was a copy-paste of the building-match count. It was checked: the two 1,681s are genuinely different sets that coincide in size, sharing only 1,205 members. The statement was correct. **Verify agent findings before acting on them.**
- **Silent string replacements.** Several `str.replace()` edits failed to match and did nothing, and the failure went unnoticed. **Always assert the anchor exists before replacing.**
- **Stale renders.** `/tmp/posterview.png` and the exported PDF went stale repeatedly while the `.pptx` moved on. Always re-export and re-render before reviewing or reporting.
- **Automated checks miss visual problems.** Avi caught two real defects by looking at rendered images that all automated checks and four review agents missed: the overlapping dots that looked like coloured rings, and the meaningless vertical positions in the beeswarm.

### Things Avi explicitly said not to do
- Do not add Claude as a git co-author.
- Do not use em dashes or semicolons in generated documents.
- Do not put the GitHub repo URL on the poster (he asked for it removed).
- Do not include the "things I'm blocked on" section in the email to Ed (he will raise those separately).

### Questions a judge is most likely to ask at the easel
1. *"Why 2.4 km? At 5 km your count goes 646 → 953."* — Answer: three radii were tested (1, 2.4, 5 km) and the middle is reported with its sensitivity shown. Buffering at all is justified because 2,284 of 2,696 sites sit on non-burnable land.
2. *"Virginia is 83% OpenStreetMap, California 48%. Is your state contrast a mapping artefact?"* — It is disclosed in Limitations. A partial defence: California's exposure is driven by a statewide seismic layer that would flag a site anywhere in the state.
3. *"Only 326 of 2,696 could be compared for footprint vs point. In what sense is this building-level?"* — 1,681 coordinates fall inside a building polygon, 993 match a nearest building within 800 m, 22 have no match. The 326 is specifically the subset where *wildfire* footprint and point sampling were both meaningful.
4. *"Walk me through the manual review of 1,150 sites."* — Be honest: an AI-assisted pipeline proposed a building and flagged its evidence, which was then reviewed. 15 were done manually. 416 came back VERIFIED.
5. *"You used an AI-assisted pipeline. What did it do, and did a human check it?"* — Expect this; the program's own seminar deck opens with AI warnings.
6. *"Water stress is basin-scale and your hazards are building-scale. Is 'largely different buildings' an artefact of comparing a polygon to a point?"* — Fair challenge. The honest answer is that no within-basin claim is made, and the state-level contrast (VA 0.7% vs 31%, IL 2.7% vs 95%) holds.

---

## 18. ANYTHING ELSE

- **Key numbers, all verified against `data/processed/` on 2026-08-04:**
  - 2,696 facilities. Sources: OpenStreetMap 1,530, PeeringDB 1,158, Wikidata 8.
  - Status: 2,680 operational, 15 under construction, 1 planned.
  - Building match: 1,681 contains / 993 nearest / 22 none. Height known for 1,327.
  - Coordinate status: 1,546 independently confirmed on building / 688 on OSM building single source / 276 no building found manual / 138 candidate suggested / 48 ambiguous.
  - Verification status: 1,546 pending / 550 CANDIDATE / 416 VERIFIED / 104 AMBIGUOUS / 80 UNRESOLVABLE.
  - Hazard exposed: **954 (35.39%)**. Wildfire 646, earthquake 448, flood 71. Two or more: 205. Exactly one: 749. None: 1,742.
  - Wildfire buffers: 1 km → 342, 2.4 km → 646, 5 km → 953.
  - WHP code 6 (non-burnable) at the building pixel: **2,284**.
  - Water stress high or extremely high: **952** (598 high + 354 extremely high). Both hazard and water: 389. Water only: 563. Either: 1,517 (**56.3%**).
  - States with ≥20 facilities: **32**. Below 10% exposed: 15. Between 10 and 60%: **7**. Above 60%: 10.
  - Monte Carlo tiers (n, mean flip probability): 10 m (870, 1.3%), 30 m (417, 5.2%), 100 m (1,372, 9.0%), 250 m (29, 25.7%), 500 m (8, 26.1%). Never changed class: 1,681. Change probability < 0.05: 2,067.
  - Footprint vs point: 2,674 with footprint stats, 326 comparable, 29 differ (8.9%).
  - Seismic validation: 150 sampled, 22 within 10%, 58 within 25%, median relative bias +31.94%, Pearson r 0.905, Spearman 0.832, RMSE 0.115 g.
  - Storm bias (within-state Spearman): tornado +0.086, hail +0.388, wind +0.340.
  - Soil sensitivity (median PGA ratio to class B): BC 1.00, C 1.056, D 1.12, E 1.09.
  - 40 sites outside FEMA's mapped extent + 8 outside the wildfire raster = 48 shown as clear with an unmapped input.
  - Merge log: 194 clusters, all with evidence.
- **Per-state figures** (hazard % / water-stress %): VA 409 sites 0.73% / 31.3%; CA 223 100% / 33.6%; NJ 91 100% / 42.9%; IL 111 2.70% / 95.5%; TX 230 5.22% / 54.8%; OH 146 0.00% / 0.0%; AZ 80 98.75% / 98.8%; OR 154 74.68% / 13.0%; WA 107 68.22% / 31.8%; FL 72 34.72% / 58.3%; NV 48 43.75% / 43.8%.
- **CA hazard breakdown:** 95.5% earthquake, 49.8% wildfire, 10.8% flood. **NJ:** 100% wildfire, 0% earthquake, 17.6% flood.
- **Git:** 59 commits on `main`, all pushed. Recent commit subjects describe each correction in detail and are a good audit trail.
- **The `~$Oughton_...pptx` lock file** appears whenever PowerPoint has the deck open. Delete it before exporting or you may ship a stale PDF.
- Avi is also running other unrelated projects (an HVAC training assistant, a Spectacles AR lens, a Dartmouth pathology agent, an ISEF research brief). **Those are not part of this project** — do not conflate them.

---

## INSTRUCTIONS FOR THE RECEIVING CHAT

**Your role.** You are a research engineering and scientific-writing collaborator for Avilash Angirekula on the US data center multi-hazard project described above. Treat this file as **authoritative context**. It supersedes any assumption you would otherwise make.

**What you can assume:**
- Everything in §14 is the exact current text of the poster and email. Reproduce it verbatim rather than paraphrasing.
- Every number in §18 was verified against `data/processed/` on 2026-08-04. If Avi has not re-run the pipeline, they are still current.
- The decisions in §6 are settled. Do not reopen them unless Avi asks or you find hard evidence they are wrong.
- The errors in §17 were real and are fixed. Do not reintroduce them.

**What you must ask Avi about rather than invent:**
- Anything requiring lab input: vulnerability curves, the dataset licence, power-capacity licensing, a landslide source.
- Whether he has sent the email, uploaded to Canvas, or checked the speaking-slot spreadsheet.
- Any change to the poster's scientific claims. Do not soften or strengthen a claim on your own judgment.
- Whether he wants Claude's involvement disclosed anywhere.
- **Never invent a citation, a standard, a threshold justification, or a domain fact.** This project has been burned by exactly that three times (the Pine Barrens, the "1.5 mile ember-cast distance", the WHP "developed" class name). If you cannot point to a file or a computed number, say you cannot.

**If you have file access to the repo:**
- Verify claims by running Python against `data/processed/`, not from memory.
- Use `./.venv/bin/python` from `~/datacenter-dataset`.
- After any poster edit: `make_poster_figures.py` → `build_poster.py` → `check_poster.py` → re-export the PDF → re-verify. Report only what you verified *after* the last edit.

**If you do not have file access (e.g. Avi is on his phone):**
- Say so plainly and answer from this file, flagging which numbers you are quoting from it rather than recomputing.
- Do not guess at file contents.

**Output style Avi prefers:**
- Concise, scannable, tables over prose.
- Exact numbers, no rounding without saying so.
- A clear recommendation, not a menu of equally weighted options.
- Explicitly separate "verified" from "not checked."
- **No em dashes. No semicolons.**
- Push back when you disagree. He has asked for this repeatedly and means it.

**A standing behavioural note.** Avi's central frustration in the previous chat was being told work was finished when it was not. The honest pattern to follow: state what you checked, state what you did not check, and never call something done on the strength of a check that ran against an earlier version.
