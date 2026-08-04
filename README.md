# US Data Center Dataset (current + planned)

A geospatially explicit, reproducible dataset of **current and planned data
centers across the contiguous US (CONUS)**. Each row is one facility with
building-level coordinates, status, descriptive attributes, and full provenance.

The dataset is designed to join cleanly against power-grid and natural-hazard
geospatial layers for a multi-hazard risk assessment of US data centers.

> **Status: dataset complete, hazard exposure attached, risk step outstanding.**
> 2,696 analysis-ready facilities across CONUS, each with a coordinate-confidence
> tier and nine natural-hazard exposure measures. 92 tests pass. Everything here
> is **exposure**, meaning what each site is subject to. No vulnerability or
> damage term is applied, so nothing in this repository is a risk or loss
> estimate. See [docs/PROJECT_STATE.md](docs/PROJECT_STATE.md) for the current
> state and [docs/hazard_exposure.md](docs/hazard_exposure.md) for method and
> limitations.

## What is in the dataset

| | |
|---|---|
| Facilities | 2,696, contiguous US |
| Coordinates inside a building polygon | 1,681 |
| Building heights measured | 1,327 |
| In a FEMA Special Flood Hazard Area | 71 |
| Within 1 km of High/Very-High wildfire land | 342 (953 within 5 km) |
| In a high or extremely-high water-stress basin | 952 |
| Largest concentration | Virginia, 409 facilities (15%) |

Hazards attached per facility: earthquake, lightning, wildfire, flood, tornado,
hail, damaging wind, tropical cyclone, and water stress.

## Project layout

```
src/dcdata/        installable package
  schema.py        canonical Facility + FacilitySource models (pydantic)
  collectors/      one module per source (base.py = interface)
  geocode/         pluggable geocoder (census default, nominatim fallback)
  resolve/         dedup + entity resolution
  validate/        CONUS bounds, lat/lon swap, MW ranges, null checks
  export.py        CSV + GeoPackage/GeoJSON via geopandas
  pipeline.py      orchestrates collect -> geocode -> resolve -> validate -> export
config/            settings.yaml (no secrets) + sources.yaml (source registry)
data/raw/          cached source responses (gitignored, reproducible)
data/interim/      per-collector normalized output
data/processed/    final CSV + GeoPackage + data-quality report
  hazards/         raster and polygon sampling used by the hazard scripts
scripts/           standalone entry points: fetch_* then build_*
docs/              data_dictionary.md, hazard_exposure.md, PROJECT_STATE.md
tests/             92 tests: parsing, dedup, schema, hazard sampling, script logic
SOURCES.md         prioritized source list with access + licensing notes
```

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate   # tested on 3.13
pip install -r requirements.txt          # geopandas pulls GDAL; may take a minute
cp .env.example .env                      # optional; no key needed for defaults
pytest                                    # run unit tests
```

## How to run

```bash
python -m dcdata.pipeline                 # rebuild the facility dataset

# hazard layers: download with checksums, then sample
python scripts/fetch_hazard_data.py
python scripts/fetch_hazard_data.py --verify
python scripts/build_hazard_exposure.py

# buildings, flood, storms, water, and the analyses
python scripts/fetch_building_attributes.py
python scripts/build_building_attributes.py
python scripts/build_footprint_hazard.py
python scripts/build_storm_exposure.py
python scripts/build_water_stress.py
PYTHONPATH=src python scripts/coordinate_uncertainty.py --draws 500
python scripts/validate_seismic.py --n 150
```

Raw hazard inputs are gitignored (about 4.4 GB). A fresh clone must run the
`fetch_*` scripts first. `zstd` is required on PATH.

## Inclusion criteria

Collect **everything**, then **tag** rather than delete:
- **Included** (curated view): commercial colocation, hyperscale, enterprise.
- **excluded_minor** (kept, flagged out of the curated view): small server rooms,
  university computer rooms, pure internet exchanges.
- **Planned** facilities are included, with unconfirmed entries flagged
  `confidence = low` and a note explaining why.

The analysis-ready dataset is the view `included == True and in_conus == True`.
The full collection is always preserved.

## Scope

Contiguous US only. AK, HI, and territories are **tagged** (`in_conus = False`)
and written to a separate file — never silently dropped — so scope can expand.

## Geocoding

Pluggable backend; default is the **free US Census geocoder** (no key), with
Nominatim/OSM as fallback. The precision actually achieved is recorded per record
in `geocode_precision`. Rooftop precision often isn't available from free
geocoders — those gaps are flagged, not faked. A paid backend can be added later
without a rewrite.

## Licensing & ethics

See [SOURCES.md](SOURCES.md). We respect robots.txt, ToS, and rate limits. We do
**not** scrape sources that prohibit it, and we never accept terms on the lab's
behalf — licensing decisions go to the lab.

## Known limitations (v0.1)

- OSM base layer mixes hyperscale campuses with minor facilities (handled via
  `excluded_minor` tagging).
- **Power capacity (MW) is currently a ROUGH MODELED ESTIMATE** from building
  footprint (≈100 W/sqft), flagged per record in `notes` — **not measured**.
  *Measured* MW needs a licensed source (Baxtel); public interconnection queues
  are generation-only (LBNL) or aggregate/confidential (ISO large-load queues).
- **`size_sqft` is the real building footprint** (ground area from OSM geometry),
  not gross floor area or IT white-space. Footprints above ~1.5M sqft are treated
  as site/campus boundaries (flagged, no MW estimate).
- `state`/`county` are reverse-geocoded from coordinates via Census TIGER
  (authoritative, ~100% within CONUS). A small number of records disagree with
  OSM's `addr:state` tag — geometry wins and the count is flagged in the report.
- Coordinate precision is capped by free geocoders until/unless a paid key is
  added; `geocode_precision` records the level actually achieved.
- **Planned coverage is thin** (~16 under-construction/proposed sites from OSM
  lifecycle tags). That is the honest license-clean ceiling; richer planned data
  needs Tier-2 directories (pending the ToS report).
- `facility_type` is operator-based. Records that name a brand only in the
  facility name (common for under-construction OSM entries like
  `Google datacenter`) classify as `unknown`. A name-based brand pass is a
  candidate future enrichment.
