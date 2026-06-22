# Data Dictionary

One row = one data center facility (building or campus). Fields mirror
`src/dcdata/schema.py` (the authoritative definition).

| field | type | notes |
|---|---|---|
| facility_id | str | stable deterministic ID (normalized name + rounded coords) |
| campus_id | str? | groups multiple buildings into one campus |
| name | str? | facility / campus name |
| operator_company | str? | owner / operator |
| facility_type | enum | traditional / hyperscale / colocation / ai_compute / enterprise / edge / excluded_minor / unknown |
| status | enum | operational / under_construction / planned / decommissioned / unknown |
| compute_capabilities | str? | processing/compute notes, e.g. "AI/GPU", "HPC", "traditional" |
| latitude | float | WGS84, building-level where possible |
| longitude | float | WGS84 |
| geom_type | enum | point / polygon (polygon = campus footprint in GeoPackage) |
| geocode_precision | enum | rooftop / parcel / address / city / county / unknown |
| **coordinate_precision** | enum | **building / campus_centroid / geocoded_address / unknown** — analysis-facing precision (see methodology below) |
| coord_confidence | enum | high / medium / low — confidence in the LOCATION specifically |
| address, city, state, county, zip | str? | state is uppercased |
| country | str | "US" |
| size_sqft | float? | per-floor building **footprint** (ground area), not gross floor area |
| area_basis | enum | gross_building / white_space / unknown |
| num_floors | int? | storeys; total floor area ≈ size_sqft × num_floors |
| power_capacity_mw | float? | measured/rated capacity (reserved for a licensed source) |
| power_basis | enum | it_load / total_facility / unknown |
| power_demand_mw | float? | "entry demand" — **modeled** estimate (footprint × floors × density), not measured |
| year_opened, planned_year | int? | |
| in_conus | bool | False = AK/HI/territory or outside CONUS bbox (kept, not dropped) |
| included | bool | type-inclusion flag; False for excluded_minor (geography tracked separately by in_conus) |
| confidence | enum | high / medium / low — record-level identity confidence |
| notes | str? | free text, incl. why a record is low-confidence |
| sources | list[FacilitySource] | provenance: source_name, source_url, source_record_id, date_accessed, confidence, raw_attributes |
| snapshot_date | date? | collection snapshot |
| dataset_version | str? | dataset semver |

**Curated view:** the analysis-ready dataset is the filter `included == True and in_conus == True`. The full collection (including `excluded_minor` and non-CONUS) is always preserved.

## Coordinate-precision methodology

`coordinate_precision` answers the question the downstream multi-hazard join
cares about: *is this point on the specific facility building, or something
coarser?* It is assigned per record by source and geometry:

| value | meaning | how it's assigned |
|---|---|---|
| `building` | on the specific facility building | OSM building footprints/nodes; manual curation marked building-level |
| `campus_centroid` | campus / site / network-building centroid | OSM polygons larger than ~1.5M sqft (site/landuse boundaries, auto-detected during footprint enrichment) |
| `geocoded_address` | derived from a street-address geocode | PeeringDB (addresses geocoded by the source) |
| `unknown` | precision not determinable | Wikidata (contributor coordinates of varying precision) |

When duplicate observations of one facility are merged, entity resolution keeps
the **most building-specific** coordinate (`building` > `geocoded_address` >
`campus_centroid` > `unknown`). Distinct buildings on one campus are **not**
merged (a name/number guard protects them), so multi-building campuses are
represented as separate building rows.

## Modeled energy demand

`power_demand_mw` is a **modeled placeholder**, not measured: it is
`footprint_sqft × num_floors × ~100 W/sqft`. It is flagged in `notes` on every
record it is set on, and is intended to be superseded by a licensed/measured
source. `power_capacity_mw` is reserved for that future measured capacity.

