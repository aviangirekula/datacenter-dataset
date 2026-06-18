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
| latitude | float | WGS84, building-level where possible |
| longitude | float | WGS84 |
| geom_type | enum | point / polygon (polygon = campus footprint in GeoPackage) |
| geocode_precision | enum | rooftop / parcel / address / city / county / unknown |
| coord_confidence | enum | high / medium / low — confidence in the LOCATION specifically |
| address, city, state, county, zip | str? | state is uppercased |
| country | str | "US" |
| size_sqft | float? | building/whitespace area |
| area_basis | enum | gross_building / white_space / unknown |
| power_capacity_mw | float? | rated/planned power capacity |
| power_basis | enum | it_load / total_facility / unknown |
| power_demand_mw | float? | actual/estimated demand ("entry demand") |
| year_opened, planned_year | int? | |
| in_conus | bool | False = AK/HI/territory or outside CONUS bbox (kept, not dropped) |
| included | bool | type-inclusion flag; False for excluded_minor (geography tracked separately by in_conus) |
| confidence | enum | high / medium / low — record-level identity confidence |
| notes | str? | free text, incl. why a record is low-confidence |
| sources | list[FacilitySource] | provenance: source_name, source_url, source_record_id, date_accessed, confidence, raw_attributes |
| snapshot_date | date? | collection snapshot |
| dataset_version | str? | dataset semver |

**Curated view:** the analysis-ready dataset is the filter `included == True and in_conus == True`. The full collection (including `excluded_minor` and non-CONUS) is always preserved.
