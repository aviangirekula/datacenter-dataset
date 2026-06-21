# Data Quality Report

## Summary
- **total_collected**: 1547
- **curated_conus**: 1532
- **non_conus**: 2
- **excluded_minor**: 13
- **collected_pre_resolve**: 1608
- **osm_operational**: 1592
- **osm_lifecycle_planned**: 16
- **merged_clusters**: 36
- **reverse_geocoded_state**: 1547
- **reverse_geocoded_county**: 1547
- **admin_conflicts_with_source**: 6
- **points_outside_any_county**: 0

## By facility_type
- unknown: 640
- colocation: 451
- hyperscale: 443
- excluded_minor: 13

## By status
- operational: 1531
- under_construction: 15
- planned: 1

## Curated CONUS — top 12 states
- VA: 341
- TX: 142
- OR: 126
- CA: 108
- OH: 89
- WA: 66
- AZ: 61
- IA: 58
- IL: 51
- NJ: 50
- GA: 38
- NV: 38

## Completeness (curated CONUS)
- name: 1291/1532 (84%)
- operator_company: 1053/1532 (68%)
- state: 1532/1532 (100%)
- address: 806/1532 (52%)
- zip: 701/1532 (45%)

## Sanity checks (full collection)
- suspected lat/lon swaps: 0
- rows missing a required field (id/lat/lon): 0
- implausible MW values: 0 (of 0 with power data)
