# Data Quality Report

## Summary
- **total_collected**: 2729
- **curated_conus**: 2696
- **non_conus**: 15
- **excluded_minor**: 20
- **collected_pre_resolve**: 2979
- **osm_operational**: 1592
- **osm_lifecycle_planned**: 16
- **peeringdb**: 1357
- **wikidata**: 14
- **manual_curation**: 0
- **merged_clusters**: 194
- **footprint_size_filled**: 1462
- **estimated_mw_filled**: 1429
- **oversized_footprints_flagged**: 33
- **reverse_geocoded_state**: 2729
- **reverse_geocoded_county**: 2729
- **admin_conflicts_with_source**: 14
- **points_outside_any_county**: 0

## By facility_type
- unknown: 1440
- colocation: 825
- hyperscale: 444
- excluded_minor: 20

## By status
- operational: 2713
- under_construction: 15
- planned: 1

## Curated CONUS — top 12 states
- VA: 409
- TX: 230
- CA: 223
- OR: 154
- OH: 146
- IL: 111
- WA: 107
- NY: 102
- NJ: 91
- IA: 81
- AZ: 80
- GA: 79

## Coordinate precision (curated CONUS)
How building-specific each coordinate is (key for the hazard join):
- building: 1501
- geocoded_address: 1158
- campus_centroid: 29
- unknown: 8

## Completeness (curated CONUS)
- name: 2477/2696 (91%)
- operator_company: 1055/2696 (39%)
- state: 2696/2696 (100%)
- address: 1999/2696 (74%)
- zip: 1906/2696 (70%)
- size_sqft: 1392/2696 (51%)
- num_floors: 106/2696 (3%)
- power_demand_mw: 1363/2696 (50%)
- compute_capabilities: 0/2696 (0%)

## Sanity checks (full collection)
- suspected lat/lon swaps: 0
- rows missing a required field (id/lat/lon): 0
- implausible MW values: 4 (of 1373 with power data)
