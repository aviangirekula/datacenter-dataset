# US Data Center Dataset (current + planned)

A geospatially explicit, reproducible dataset of **current and planned data
centers across the contiguous US (CONUS)**. Each row is one facility with
building-level coordinates, status, descriptive attributes, and full provenance.

Built for **Prof. Edward Oughton's GeoAI lab (George Mason University)** as input
to a multi-hazard risk assessment of US data centers (power-grid interaction +
natural-hazard exposure). The dataset is designed to join cleanly against
power-grid and natural-hazard geospatial layers.

> **Status: v0.1 scaffold.** Schema, config, validation, and the OpenStreetMap
> base layer (1,592 CONUS facilities, cached) are in place. The end-to-end
> collector→geocode→resolve→validate→export pipeline is being built one source at
> a time, starting with OpenStreetMap.

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
docs/              data_dictionary.md
tests/             parsing + dedup + schema unit tests
SOURCES.md         prioritized source list with access + licensing notes
```

## Setup

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # geopandas pulls GDAL; may take a minute
cp .env.example .env                      # optional; no key needed for defaults
pytest                                    # run unit tests
```

## How to run (as the pipeline lands)

```bash
python -m dcdata.pipeline                 # full run: collect -> ... -> export
```

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
- **No per-facility energy/capacity data yet.** Public interconnection queues are
  *generation-only* (LBNL) or *aggregate/confidential* (ISO large-load queues), so
  energy enters as a separate **grid-context layer** on the roadmap — not as
  facility rows. See [SOURCES.md](SOURCES.md).
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
