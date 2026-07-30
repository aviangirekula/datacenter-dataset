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
| Facilities with High/Very-High (class >= 4) burnable land in radius | 333 | 656 | 954 |

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
2. **Seismic values are reference rock.** Site class BC (Vs30 760 m/s). Many
   large clusters sit on soft ground (Santa Clara, Chicago lakebed, Phoenix and
   Dallas basins), where site amplification at short periods is materially higher.
   Reported values are therefore a systematic, spatially correlated
   **underestimate** at those sites. A Vs30 join and a BC-versus-D sensitivity
   comparison are needed before publication.
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
5. **Positional accuracy varies and is not yet propagated.** The table carries
   the verification tier, but hazard values are not re-sampled under coordinate
   uncertainty. A Monte Carlo perturbation by tier is the planned robustness
   check. Expect it to be a no-op for seismic and lightning and material for
   wildfire.
6. **Eight facilities sample on an open-water pixel** (flagged
   `qa_coordinate_on_water`). These are coordinate errors surfaced by the
   sampling, kept and flagged rather than silently dropped.
7. **No exposure weighting.** `power_capacity_mw` is entirely null, so every
   statistic counts a small colocation suite the same as a hyperscale campus.
   Capacity-weighted statements are not currently supportable.
8. **Validation is qualitative so far.** Values reproduce known US hazard
   geography (seismic peaks in California, coastal South Carolina, the Pacific
   Northwest, Utah and the New Madrid zone; lightning peaks on the Gulf Coast).
   A quantitative check against an independent point source, with bias and RMSE
   over a random sample, is still required.

## Not yet included

- **Flood.** The most consequential hazard for this asset class, and absent. The
  WRI Aqueduct URL used upstream has been retired and the layer is not in the
  MHTran archive. FEMA NFHL is the strongest replacement (national, polygon,
  suited to footprint intersection). Not substituted with an arbitrary layer.
- **Tornado, hail, damaging wind, tropical cyclone.** Published as historical
  event tracks (NOAA SPC/SVRGIS, IBTrACS), not hazard surfaces. Converting them
  to per-facility exposure needs an explicit frequency method (event rate per
  unit area within a radius), or the ASCE 7-22 design wind-speed surfaces for
  wind. Method to be aligned before implementation.
- **Landslide, water stress, geomagnetic.** Straightforward additions; water
  stress is worth including given evaporative-cooling demand.

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
