# Candidate Data Sources

Prioritized source list with access method and licensing notes. Build **Tier 1
(open / license-clean) first**. Tier 2 directories are richer but ToS-restricted:
we **check their terms and report**, we do **not** scrape them, and we do **not**
accept any terms on the lab's behalf.

## Tier 1 — open / authoritative (build first)

| # | Source | Provides | Access method | License | Status |
|---|--------|----------|---------------|---------|--------|
| 1 | **OpenStreetMap** (Overpass API) | building/campus coordinates & polygons, name, operator, address | Overpass API (HTTP POST, User-Agent required) | ODbL (attribution + share-alike) | ✅ pulled — 1,592 CONUS elements cached |
| 2 | **Interconnection queues** — LBNL "Queued Up" + ISO/RTO (PJM, ERCOT, MISO, SPP, NYISO, ISO-NE, CAISO) | **planned** large loads, **MW capacity**, county location, queue date | LBNL data download + ISO public queue files | US-gov / public | Highest priority for planned + power |
| 3 | **EIA** (Forms 860/861, data-center load reports) | grid/load context, regional generation | EIA Open Data API (free key) + bulk CSV | Public domain | Grid join layer |
| 4 | **SEC EDGAR** (10-Ks: Equinix, Digital Realty, etc.) | operator facility portfolios, sqft | EDGAR full-text search API | Public domain | Operator enrichment |
| 5 | **Operator location pages** (AWS, Google, Meta, Microsoft) | self-published facility/region locations | their own published pages | per-site ToS (own published data) | Medium; often city/region grain |
| 6 | **US Census** (TIGER boundaries + Geocoder) | county/ZIP joins; free US street geocoding | API, no key | Public domain | Infrastructure (geocoding + admin joins) |

## Tier 2 — commercial directories (ToS report only; not scraped)

| # | Source | Provides | Concern / action |
|---|--------|----------|------------------|
| 7 | **Baxtel** | coords, MW, sqft, status | Almost certainly bars scraping — pending robots.txt/ToS review; use only via license or manual export |
| 8 | **DataCenterMap** | coords, operator | Same — pending ToS review |
| 9 | **Cloudscene / Datacenters.com / DCD database** | listings, planned-facility news | Proprietary — manual reference only unless licensed |

**Next action on Tier 2:** review each site's `robots.txt` and Terms of Service
and report back which would *meaningfully* improve coverage and what their
licensing requires. No data pulled until you take any licensing decision to the lab.

## Open items (swappable by design; flagged where they affect output)
- (a) Paid geocoder key — not required; free-geocoder precision (parcel/address,
  sometimes city) is the current ceiling. Rooftop gaps are flagged in
  `geocode_precision`.
- (b) Commercial directory license/export — pending lab decision.
- (c) Final repo home (lab GitHub org vs. personal) — local only until confirmed.
