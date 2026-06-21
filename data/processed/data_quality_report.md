# Data Quality Report

## Summary
- **total_collected**: 1556
- **curated_conus**: 1541
- **non_conus**: 3
- **excluded_minor**: 14
- **collected_pre_resolve**: 1622
- **osm_operational**: 1592
- **osm_lifecycle_planned**: 16
- **peeringdb**: 0
- **wikidata**: 14
- **merged_clusters**: 40
- **reverse_geocoded_state**: 1556
- **reverse_geocoded_county**: 1556
- **admin_conflicts_with_source**: 6
- **points_outside_any_county**: 0

## By facility_type
- unknown: 647
- colocation: 451
- hyperscale: 444
- excluded_minor: 14

## By status
- operational: 1540
- under_construction: 15
- planned: 1

## Curated CONUS — top 12 states
- VA: 341
- TX: 142
- OR: 126
- CA: 109
- OH: 89
- WA: 66
- AZ: 61
- IA: 58
- IL: 51
- NJ: 50
- GA: 38
- NV: 38

## Completeness (curated CONUS)
- name: 1300/1541 (84%)
- operator_company: 1056/1541 (68%)
- state: 1541/1541 (100%)
- address: 807/1541 (52%)
- zip: 702/1541 (45%)

## Sanity checks (full collection)
- suspected lat/lon swaps: 0
- rows missing a required field (id/lat/lon): 0
- implausible MW values: 0 (of 0 with power data)
