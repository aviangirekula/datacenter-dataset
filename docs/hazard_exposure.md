# Multi-hazard exposure

Per-facility natural-hazard **exposure** for the data-center dataset. Produced by
`scripts/build_hazard_exposure.py`; outputs `data/processed/hazard_exposure.csv`
(one row per facility) and `data/processed/hazard_exposure_coverage.json`
(machine-readable coverage and provenance for the run).

> **Scope.** These are exposure values, not risk. No vulnerability or
> consequence term is applied, so nothing here is a damage or loss estimate.
> Converting exposure to risk needs vulnerability curves, which are a later step.

## Method

Each hazard layer is sampled at the facility coordinate (WGS84), reprojecting the
point into the layer's own CRS. Two access patterns, in `src/dcdata/hazards/sample.py`:

- **Raster** hazards: value of the pixel under the point, or zonal statistics in
  a buffer where the hazard to a structure is driven by its surroundings.
- **Polygon** hazards: value of the polygon the point falls inside.

Rules that the published numbers depend on, all covered by tests in
`tests/test_hazards.py`:

- Nodata and out-of-bounds are **always NaN**, never zero-filled.
- Imputation is **opt-in**, distance-capped, measured in metres (not degrees),
  and flagged in a `_method` column. Coverage is therefore reported as
  *measured* and *imputed* separately, not as a single percentage.
- Documented no-data regions are never back-filled from a neighbour.
- Positional-accuracy fields (`coordinate_precision`, `verification_status`,
  `coord_confidence`) are carried into the output so downstream analysis can
  restrict to building-verified coordinates.

## Hazards included

| Hazard | Column(s) | Source | Native resolution | Coverage |
|---|---|---|---|---|
| Earthquake | `haz_seismic_pga_g_475yr`, `_975yr`, `_2475yr` (+ `_method`) | USGS NSHM 2023, site class BC | 0.2 deg grid, contoured | 2,696 measured, 0 imputed |
| Lightning | `haz_lightning_flash_per_km2_yr` | NASA LIS/OTD via MHTran archive | 0.5 deg (~50 km) | 2,696 measured |
| Wildfire | `haz_wildfire_whp_code`, `_severity`, `haz_wildfire_surface`, `haz_wildfire_burnable_frac_{1000,2400,5000}m`, `haz_wildfire_max_severity_{...}m` | USFS WHP 2023 | 270 m | 2,696 sampled; 404 carry an ordinal severity |

### Reading the wildfire columns

WHP codes 1-5 are an **ordinal** severity ladder (Very Low to Very High). Codes
**6 (non-burnable / developed) and 7 (open water) are nominal surface classes**,
not a continuation of that ladder. Averaging or ranking the raw code is therefore
invalid, and would assert that "developed" is worse than "Very High". The columns
are split accordingly:

- `haz_wildfire_whp_code` - raw code, for traceability only.
- `haz_wildfire_whp_severity` - 1-5 only, NaN for 6/7. **Use this for statistics.**
- `haz_wildfire_surface` - the categorical label.

Because data centers are buildings in developed areas, 2,284 of 2,696 (85%)
return code 6 at the pixel under the building. The pixel class is therefore a
weak structure-risk metric on its own: wildland-urban-interface loss is driven by
ember cast and spread from the **surroundings**. The buffer columns capture that:

| Metric | 1 km | 2.4 km | 5 km |
|---|---|---|---|
| Facilities with High/Very-High (class >= 4) burnable land in radius | 342 | 646 | 953 |

### Return periods

Three exceedance levels are sampled (10%, 5% and 2% in 50 years, i.e. ~475, ~975
and ~2,475-year mean return periods). Reporting more than one matters here:
data centers are ASCE 7 Risk Category III/IV and are designed against the
risk-targeted maximum considered earthquake, which is anchored near the 2%-in-50-year
level, so a 475-year-only view understates the design-relevant hazard.

## Known limitations

These are stated plainly because they bound what the data can support.

1. **Point sampling, not footprint intersection.** Values are sampled at one
   coordinate per facility. This is adequate where the hazard's correlation
   length greatly exceeds a building (seismic, lightning) and is a real
   limitation where it does not (wildfire at 270 m; flood, once added, varies at
   ~10 m). Attaching real building polygons (e.g. ORNL/FEMA USA Structures) and
   doing area-weighted zonal statistics is the planned fix.
2. **Seismic values are reference rock, and the soil effect is now measured.**
   Site class BC (Vs30 760 m/s). Querying the same 150 points across site
   classes gives median PGA ratios of 1.00 (B), 1.06 (C), 1.12 (D) and 1.09 (E)
   relative to rock, so reference-rock values understate soft-soil motion by
   about 12% at these locations. Class E falling below D reflects nonlinear soil
   de-amplification at higher shaking. A full Vs30 join per facility is still
   preferable to a uniform sensitivity.
3. **Seismic values are contour-band midpoints.** Bands are a uniform 0.01 g, so
   discretisation is +/-0.005 g. For the 116 facilities in the lowest band that is
   a +/-100% relative uncertainty. The underlying gridded model and full hazard
   curves are available from USGS and are preferable to the cartographic contours.
4. **Lightning is regional, not building-scale.** A 0.5 degree (~50 km) grid
   yields only 385 distinct values across 2,696 facilities, and one cell contains
   145 of them. It should be interpreted at regional level. LIS/OTD is also
   orbital, and most facilities lie north of the LIS field of view, so their
   values rest on the sparser OTD record. A ground-network product (e.g. NLDN)
   would be the building-scale alternative.
5. **Positional accuracy is now propagated.** A 50-draw Monte Carlo perturbs
   each coordinate by a tier-appropriate sigma (10 m where the coordinate falls
   inside a building, up to 500 m unresolved) and re-samples. Wildfire class
   changes in 3.2% of draws on average, 2,367 of 2,696 facilities are stable,
   and the change probability rises monotonically with positional sigma
   (1.1 / 5.2 / 8.1 / 27.6 / 36.7%). Lightning has a relative standard deviation
   of 0.0000, so the coarse grid is provably insensitive. See
   `scripts/coordinate_uncertainty.py`.
6. **Eight facilities sample on an open-water pixel** (flagged
   `qa_coordinate_on_water`). These are coordinate errors surfaced by the
   sampling, kept and flagged rather than silently dropped.
7. **No exposure weighting.** `power_capacity_mw` is entirely null, so every
   statistic counts a small colocation suite the same as a hyperscale campus.
   Capacity-weighted statements are not currently supportable.
8. **Validation is now quantitative.** 150 random facilities were checked
   against the USGS ASCE 7-22 web service, which delivers the same underlying
   model independently of the shapefiles: Pearson r 0.896, Spearman 0.796,
   RMSE 0.108 g, median bias +25%. The offset is expected, because our column
   is uniform-hazard reference-rock while the service returns a risk-targeted
   site-modified value. Rank agreement is the meaningful result. See
   `scripts/validate_seismic.py`.

## Building attributes and flood

`scripts/fetch_building_attributes.py` + `build_building_attributes.py` produce
`data/processed/building_attributes.csv`.

| Field | Meaning |
|---|---|
| `building_match` | `contains` (coordinate inside a building polygon), `nearest`, or `none` |
| `building_match_confidence` | `high` if contained or within 200 m, `low` beyond that |
| `footprint_sqft`, `height_m` | of the matched building, geodesic area with holes subtracted |
| `largest_nearby_sqft`, `largest_nearby_dist_m`, `largest_nearby_height_m` | the **largest** building in the search radius |
| `flood_zone`, `flood_sfha`, `flood_mapped` | FEMA NFHL layer 28, using FEMA's own `SFHA_TF` flag |

Results: 1,681 coordinates fall inside a building, 993 match a nearest building
within 800 m, 22 have no match. Height is measured for 1,327 facilities (49%).
FEMA maps 2,624 of them, of which **71 lie inside a Special Flood Hazard Area**
(the regulatory 1% annual chance floodplain).

**Why two building columns.** At a hyperscale campus the recorded coordinate is
often a gate, so the *nearest* structure is a guardhouse while the data hall is
the large box behind it. For the 234 low-confidence matches the nearest building
has a median footprint of 1,978 sqft while the largest within the radius has a
median of 50,029 sqft, and 84 of them exceed 100,000 sqft. Forcing a single
choice would be wrong either way, so both are recorded and the analysis picks.
Widening the search from 200 m to 800 m cut misses from 256 to 22 and did not
change any containment result, which is the expected self-consistency check.

## Not yet included

(Flood, storm and tropical-cyclone hazards are now included, see above.)
- **Landslide, water stress, geomagnetic.** Still outstanding. The USGS
  landslide ScienceBase item and the WRI Aqueduct water-risk download did not
  resolve at their published URLs and need a working source.

## Reproduce

```bash
./.venv/bin/python scripts/fetch_hazard_data.py            # download + checksum
./.venv/bin/python scripts/fetch_hazard_data.py --verify   # verify only
./.venv/bin/python scripts/build_hazard_exposure.py        # build the table
pytest tests/test_hazards.py -q
```

`scripts/fetch_hazard_data.py` carries the canonical URL, byte size, MD5, DOI,
licence and target path for every layer. Download is about 1.3 GB; about 2.8 GB
on disk after extraction. Raw layers are gitignored. `zstd` is required for the
Zenodo archive.

## Data sources and citation

Derived values in `hazard_exposure.csv` come from these sources, which must be
cited in any publication using this table.

- **Oughton, E. J., & Weigel, R. (2026).** *A Comparative Multi-Hazard Risk
  Assessment of the US High-Voltage Transmission Network* (v1) [Data set].
  Zenodo. doi:10.5281/zenodo.20331026. **Licensed CC BY 4.0, which requires
  attribution on derived works.** Supplies the LIS/OTD lightning raster used
  here; that file is itself a reprojection of the NASA LIS/OTD climatology,
  which should be cited alongside it.
- **Petersen, M. D., et al. (2023).** *2023 US National Seismic Hazard Model.*
  US Geological Survey data release. doi:10.5066/P9GNPCOD.
- **Dillon, G. K. (2023).** *Wildfire Hazard Potential for the United States
  (270-m), version 2023, 4th Edition.* Forest Service Research Data Archive.
  doi:10.2737/RDS-2015-0047-4.
