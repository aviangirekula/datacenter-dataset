# Project state

Handoff document. Everything below was verified against the repo, not recalled.
Last verified: 2026-08-02.

## Repo

| | |
|---|---|
| Root | `~/datacenter-dataset` |
| Remote | https://github.com/aviangirekula/datacenter-dataset (public) |
| Branch | `main` |
| HEAD | `c6985e1` "Add baseline water stress from WRI Aqueduct 4.0" |
| Working tree | clean, in sync with `origin/main` |
| Tests | 72 passed |

## What this project is

A geospatially explicit dataset of **2,696 US data centers** (contiguous US) with
building-level coordinates, per-record confidence, and natural-hazard exposure.
Built for Prof. Edward Oughton's GeoAI lab at George Mason University, feeding a
multi-hazard risk assessment paper. Everything produced so far is **exposure**,
meaning what each site is subject to. No vulnerability or damage term is applied,
so nothing here is a risk or loss estimate.

## Architecture and data flow

```
  collectors (OSM, OSM lifecycle, PeeringDB, Wikidata, manual CSV)
        |
        v
  dcdata.pipeline  ->  dedup (rapidfuzz + haversine)
        |                enrich/footprint (geodesic area, modeled MW)
        |                geocode/reverse (Census TIGER -> state, county)
        v
  data/processed/datacenters_final.csv        2,696 facilities  <-- the spine
        |
        +--> scripts/fetch_hazard_data.py        raw hazard layers + checksums
        |    scripts/build_hazard_exposure.py -> hazard_exposure.csv
        |
        +--> scripts/fetch_building_attributes.py  (ArcGIS, cached JSONL)
        |    scripts/build_building_attributes.py -> building_attributes.csv
        |
        +--> scripts/build_footprint_hazard.py  -> footprint_hazard.csv
        |                                          building_footprints.gpkg
        +--> scripts/build_storm_exposure.py    -> storm_exposure.csv
        +--> scripts/build_water_stress.py      -> water_stress.csv
        +--> scripts/coordinate_uncertainty.py  -> coordinate_uncertainty.csv
        +--> scripts/validate_seismic.py        -> seismic_validation.json
```

Every facility is keyed by `facility_id`. All derived tables join back to
`datacenters_final.csv` on that key. Scripts are standalone entry points; the
package (`src/dcdata/`) holds the reusable pipeline and sampling library.

## Commands that work

Run from the repo root. The venv is at `.venv` (Python 3.13.5).

```bash
# setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# tests
./.venv/bin/python -m pytest tests/ -q

# lint (configured in pyproject.toml, line-length 100)
./.venv/bin/python -m ruff check src/ scripts/ tests/

# hazard layers: download with checksum verification, then build
./.venv/bin/python scripts/fetch_hazard_data.py
./.venv/bin/python scripts/fetch_hazard_data.py --verify
./.venv/bin/python scripts/build_hazard_exposure.py

# buildings + flood (ArcGIS; resumable, cache keyed by radius)
./.venv/bin/python scripts/fetch_building_attributes.py
./.venv/bin/python scripts/fetch_building_attributes.py --only structures --radius 800 --ids-file IDS.txt
./.venv/bin/python scripts/build_building_attributes.py

# authoritative seismic (USGS ASCE 7-22, one call per facility, resumable)
./.venv/bin/python scripts/fetch_seismic_authoritative.py

# analyses
./.venv/bin/python scripts/build_footprint_hazard.py
./.venv/bin/python scripts/build_storm_exposure.py
./.venv/bin/python scripts/build_water_stress.py
PYTHONPATH=src ./.venv/bin/python scripts/coordinate_uncertainty.py --draws 500
./.venv/bin/python scripts/validate_seismic.py --n 150

# figure
./.venv/bin/python scripts/make_wildfire_figure.py
```

`coordinate_uncertainty.py` imports `dcdata.hazards.sample`, so it needs
`PYTHONPATH=src` unless the package is installed. The other scripts do not.

## Environment

Python 3.13.5. Verified versions: pandas 3.0.3, numpy 2.4.6, geopandas 1.1.3,
shapely 2.1.2, pyproj 3.7.2, rasterio 1.5.0, scipy 1.18.0, pyogrio 0.12.1,
pydantic 2.13.4, rapidfuzz 3.14.5, GDAL 3.12.1, PROJ 9.5.1.

`zstd` is required on PATH to extract the Zenodo hazard archive.

Env var names (never commit values): `PEERINGDB_API_KEY`, optional, the
collector degrades gracefully without it.

## Files created or modified this session

**Library**
- `src/dcdata/hazards/__init__.py` — package docstring stating scope and honesty rules
- `src/dcdata/hazards/sample.py` — raster point sampling, buffer zonal stats, polygon join

**Fetchers**
- `scripts/fetch_hazard_data.py` — hazard layers with URLs, byte sizes, MD5s, DOIs, licences; `--verify`
- `scripts/fetch_building_attributes.py` — USA Structures + FEMA NFHL per facility, cached JSONL keyed by radius
- `scripts/fetch_seismic_authoritative.py` — USGS ASCE 7-22 per facility, cached JSONL

**Builders / analyses**
- `scripts/build_hazard_exposure.py` — seismic, lightning, wildfire + WUI buffers, authoritative seismic merge
- `scripts/build_building_attributes.py` — picks one building per facility, flood zone, height
- `scripts/build_footprint_hazard.py` — area-weighted footprint zonal stats, storey control
- `scripts/build_storm_exposure.py` — tornado, hail, wind, tropical cyclone
- `scripts/build_water_stress.py` — WRI Aqueduct basin join
- `scripts/coordinate_uncertainty.py` — Monte Carlo positional-error propagation
- `scripts/validate_seismic.py` — external validation and soil sensitivity
- `scripts/make_wildfire_figure.py` — two-panel slide figure

**Tests**
- `tests/test_hazards.py` — 19 tests on the sampling library
- `tests/test_hazard_exposure_output.py` — invariants on the published table

**Docs / config**
- `docs/hazard_exposure.md` — method, sources, limitations, citations
- `docs/data_dictionary.md` — hazard field definitions appended
- `SOURCES.md` — hazard source table with DOIs and licences appended
- `requirements.txt` — added `rasterio`, `scipy`, `pyogrio`
- `.gitignore` — ignores `data/hazards/`, `data/raw/buildings/`

**Outputs** (committed): `hazard_exposure.csv`, `building_attributes.csv`,
`footprint_hazard.csv`, `storm_exposure.csv`, `water_stress.csv`,
`coordinate_uncertainty.csv`, `seismic_validation.csv`,
`building_footprints.gpkg`, `data/raw/seismic_points.jsonl`, plus a
`*_coverage.json` beside most of them, and `figures/wildfire_exposure.png`.

## Test status

72 passing. Coverage is **library-only**:

- Covered: `dcdata.hazards.sample` (nodata, out-of-bounds, exact-edge, CRS
  reprojection, zero preservation, buffer centring across sub-pixel alignments,
  imputation policy, invalid-geometry repair), plus the pre-existing collector,
  dedup, schema, precision and reverse-geocode tests.
- Covered indirectly: the published `hazard_exposure.csv` via invariants
  (severity null iff nominal code, water flag matches code 7, seismic monotonic
  across return periods, imputation always flagged, buffer severity monotonic in
  radius). Skips automatically if the CSV is absent.
- **Untested: every file in `scripts/`.** No test imports or executes any script.
  About 2,000 lines of analysis code rest on manual verification and adversarial
  review rather than automated tests.

## Known issues and gaps

**Blocking for publication**
- `haz_seismic_pga_g_475yr` and `_975yr` are still sampled from a cartographic
  **contour** product (0.01 g bands). At the 2,475-year level the contour values
  agreed with the authoritative USGS figure within 10% for only 425 of 2,696
  (16%), median bias +29%, range −54% to +189%. Use
  `haz_seismic_pga_g_2475yr_usgs` instead. The two shorter return periods have no
  public point service and remain approximate.
  See `docs/hazard_exposure.md` limitation 8.
- **Landslide is absent and could not be obtained.** USGS ScienceBase items time
  out, the direct download returns 403, and the ArcGIS layer
  (`US_Landslide_Susceptibility`) is a cached tile service with no query
  capability. Needs a source from the lab.
- **No LICENSE file.** 1,530 of 2,696 records derive from OpenStreetMap (ODbL,
  share-alike), so the choice may be constrained. Lab decision.
- **`power_capacity_mw` is null for every record**, so no statistic can be
  weighted by facility size. Only facility counts are supportable.

**Method caveats, documented in `docs/hazard_exposure.md`**
- Storm exposure is a regional areal density, not a site strike rate. Only the
  tornado path-area column is a site quantity.
- SPC reporting bias is **not** controlled. Significant hail and wind counts rise
  24–26% per decade even in the modern era.
- Lightning is a 0.5 degree (~50 km) grid: regional, not building-scale.
- Tropical cyclone track proximity is not landfall intensity.
- 8 facilities sample on an open-water pixel, flagged `qa_coordinate_on_water`.
- 234 building matches are low confidence (beyond 200 m); 22 have no match.

**Code smells left in place**
- Nine bare `except Exception:  # noqa: BLE001` handlers across `scripts/`.
  `build_footprint_hazard.py:77`, `:101` swallow geometry parse failures without
  a counter. `:199` does count into `errs` and warns.
- `scripts/build_footprint_hazard.py` zonal stats loop is O(cells) in Python and
  takes minutes over 2,674 footprints.
- `README.md` still describes the project as "v0.1 scaffold" and says
  `python3.11`; both are stale.
- No `TODO`/`FIXME`/`HACK` markers exist anywhere in the tree.

## Conventions a fresh session would violate

1. **Never claim a check that was not run.** Three docstrings in this project
   asserted things the code did not do ("area-weighted" when it was unweighted,
   "risk-targeted" for a quantity that is not, "that is checked" for a check that
   never happened). All were caught by review. Write what the code does.
2. **Nodata is NaN, never 0.** Imputation is opt-in, distance-capped, measured in
   metres, and flagged in a `_method` column. Coverage is reported as *measured*
   versus *imputed*, never one blended percentage.
3. **Ordinal and nominal codes never mix.** WHP 1–5 is a severity ladder; 6
   (developed) and 7 (water) are surface categories. Averaging across them is
   invalid and produced a badly inflated result once already.
4. **Adversarial review before calling anything done.** The user requires it.
   Every round so far found real defects, including in the fixes themselves.
   Mutation-test new tests: deliberately reintroduce the bug and confirm the test
   fails. One centring test passed under the exact bug it was written for.
5. **Distances in metres, in a projected CRS** (EPSG:5070 for CONUS). Never
   compute distance in degrees. Measure to building **edges**, not centroids.
6. **Parse all polygon rings.** Using `rings[0]` alone drops courtyards and
   multipart geometry; it overstated one footprint by 44%.
7. **Prefer a source's own authoritative flag** over a derived heuristic
   (FEMA `SFHA_TF`, not an A/V zone-prefix rule).
8. **Raw hazard inputs are gitignored** (4.4 GB in `data/hazards/`, 185 MB in
   `data/raw/buildings/`). A fresh clone has none of them; run the fetchers.
   Derived CSVs and the seismic point cache **are** committed.
9. **No em dashes and no semicolons** in generated prose, per the user's
   standing preference.
10. **Do not add Claude as a git co-author.** Removed from history previously.

## Next steps

Requires the lab: vulnerability curves (the actual risk step), the licence
choice, the Tier-2 directory citation question, and whether to license Baxtel for
measured power. Three draft emails covering these are in the user's Gmail.

Doable without anyone: sample the NSHM grid for the 475 and 975 year seismic
levels, add landslide once a source exists, and write tests for `scripts/`.

Immediate deadline: the ASSIP poster is due Tuesday 2026-08-04 at 5 pm. The user
leads that.
