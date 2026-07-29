# Multi-hazard exposure

Per-facility natural-hazard exposure for the data-center dataset. Produced by
`scripts/build_hazard_exposure.py`, output at `data/processed/hazard_exposure.csv`
(one row per facility, one column per hazard).

## Approach

Each hazard layer is sampled at every facility's building-level coordinate
(WGS84). Hazard layers come from the same public sources used by the lab's
transmission study (Bor, Oughton & Weigel, MHTran, Zenodo 10.5281/zenodo.20331026),
so results stay methodologically consistent, but applied to data-center
locations instead of substations.

Two sampling patterns (`src/dcdata/hazards/sample.py`):
- **Raster** hazards: reproject the point into the raster CRS, read the pixel
  under it. Nodata and out-of-bounds become null (never zero-filled).
- **Polygon** hazards: point-in-polygon; a facility takes its band's value.

Coverage (non-null count) is reported per hazard on every run.

## Hazards included

| Hazard | Column | Source | Metric | Coverage |
|---|---|---|---|---|
| Earthquake | `haz_seismic_pga_g_475yr` | USGS NSHM 2023 | Peak ground acceleration (g), 10% in 50 yr (~475-yr return), site class BC | 100% |
| Lightning | `haz_lightning_flash_per_km2_yr` | NASA LIS/OTD climatology | Mean annual flash density (flashes/km2/yr) | 100% |
| Wildfire | `haz_wildfire_whp_class` | USFS Wildfire Hazard Potential 2023 (270 m) | WHP class (see below) | 100% |

Values were checked against known US geography: seismic peaks in CA, coastal SC
(Charleston), the Pacific NW, Utah and the New Madrid zone, and is near zero on
the stable interior; lightning peaks on the Gulf Coast and is near zero on the
West Coast. Both match published hazard maps.

### Wildfire class codes
1 Very Low, 2 Low, 3 Moderate, 4 High, 5 Very High, 6 non-burnable
(developed/urban/agriculture), 7 open water. Because data centers are buildings
in developed areas, most (about 85%) sample as class 6 at the exact pixel. A
building-relevant wildfire metric usually looks at the surrounding
wildland-urban interface (WHP within a buffer), which is a planned refinement to
align with Dennies.

## Not yet included

- **Flood** (WRI Aqueduct): the old public download URL has been retired and the
  layer is not in the MHTran archive. Needs the exact source/file from Dennies
  before it can be sampled correctly. Not faked with a substitute layer.
- **Tornado, hail, damaging wind, tropical cyclone**: distributed as historical
  storm-event records (tracks), not a single hazard surface. Converting these to
  a per-building exposure needs a frequency method (e.g. events within a radius
  over a period). That method choice should be aligned with Dennies before
  implementation.
- **Landslide, geomagnetic, drought**: lower priority; landslide susceptibility
  is a straightforward add when needed.

## Reproduce

```bash
./.venv/bin/python scripts/build_hazard_exposure.py
```

Raw hazard layers live under `data/hazards/` (gitignored, ~1.3 GB). Re-download:
MHTran archive from Zenodo 10.5281/zenodo.20331026 (lightning), USGS ScienceBase
item 64ff886dd34ed30c2057b4d9 (seismic), USFS RDS-2015-0047-4 (wildfire).
