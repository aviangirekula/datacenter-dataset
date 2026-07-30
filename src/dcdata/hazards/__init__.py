"""Multi-hazard exposure for data-center facilities.

Samples natural-hazard layers at each facility coordinate to produce a
facility x hazard exposure table. Layers come from the same public sources used
by the lab's transmission study (Oughton, E. J., & Weigel, R. (2026),
*A Comparative Multi-Hazard Risk Assessment of the US High-Voltage Transmission
Network*, Zenodo, doi:10.5281/zenodo.20331026, CC BY 4.0), so this analysis stays
methodologically consistent with it while being applied to data-center locations
rather than substations.

IMPORTANT - scope and honesty:
- These columns are EXPOSURE, not risk. No vulnerability or consequence term is
  applied, so they must not be reported as damage or loss estimates.
- Values are sampled at a single facility point, not intersected with a building
  footprint. That is adequate where the hazard varies slowly relative to a
  building (seismic, lightning) and is a documented limitation where it does not
  (wildfire at 270 m, and flood once added).
- Nodata and out-of-bounds are always NaN. Imputation is opt-in, distance-capped
  and flagged, so measured coverage is reported separately from imputed.
- Hazard values inherit the positional accuracy of the coordinate, so the
  facility verification tier is carried into the output table.
"""
