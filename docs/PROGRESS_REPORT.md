# US Data Center Dataset — Progress Report

**Author:** Avilash Angirekula (ASSIP, Prof. Edward Oughton's GeoAI lab, GMU)
**Date:** 2026-06-20
**Repo:** `~/datacenter-dataset/` (local Git, not yet pushed — 7 commits)

---

## 1. Objective

Build a geospatially explicit, reproducible **Python** dataset of **current and
planned US data centers (CONUS)** at **building-level** coordinates, with
descriptive attributes (company, status, size, power) and **provenance for every
record** — designed to join downstream against power-grid and natural-hazard
layers for a multi-hazard risk-assessment paper.

---

## 2. What's been done

### Against the original 8-part task plan

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Plan + prioritized source list | ✅ Done | `SOURCES.md`; Tier-1 open vs Tier-2 restricted |
| 2 | Repo scaffold | ✅ Done | `src/ data/ config/ tests/ notebooks/ docs/`, README, requirements, .gitignore |
| 3 | Modular collectors (common schema, raw cache) | ⚠️ Partial | OSM operational + OSM lifecycle built; framework ready for more sources |
| 4 | Geocoding (pluggable, record precision, no keys) | ⚠️ Partial | Reverse-geocoding (TIGER) live; forward (Census) written, not yet needed |
| 5 | Deduplication / entity resolution | ✅ Done | rapidfuzz + haversine, building-number guard, full audit log |
| 6 | Validation + data-quality report | ✅ Done | CONUS bounds, lat/lon swap, MW range, null checks |
| 7 | Outputs (CSV + GeoPackage + GeoJSON, data dictionary) | ✅ Done | all three formats + `data_dictionary.md` |
| 8 | Documentation | ✅ Done | README, SOURCES, ToS report, data dictionary |

Schema (`schema.py`): ✅ all requested fields + 6 agreed improvements (separate
provenance, `area_basis`/`power_basis`, `campus_id`, `geom_type`,
`coord_confidence`, versioning).

### Pipeline (runs end-to-end: `python -m dcdata.pipeline`)

```
OSM operational  ┐
OSM lifecycle    ┘→ entity resolution → reverse-geocode → validate → export
(planned)          (dedup + log)        (state/county)    (QA report)  (CSV/GPKG/GeoJSON)
```

- Reproducible: raw responses cached; Git-tracked; **31 passing unit tests**
- Engineering quality: conservative dedup preserves building-level granularity
  and all source URLs; every merge logged; coordinates never overwritten

---

## 3. Current dataset snapshot

- **1,547 facilities total** — 1,531 operational, 16 planned/under-construction
- **By type:** 451 colocation, 443 hyperscale, 640 unknown, 13 excluded_minor
- **Coverage / completeness (curated CONUS, n=1,532):**
  - coordinates (building-level): 100%
  - state / county: **100%** (reverse-geocoded via Census TIGER)
  - name: 84% · operator: 69% · street address: 53% · zip: 46%
- **Provenance + confidence flags:** every record
- **Power capacity (MW): 0%** · **Size (sq ft): 0%** — no open source provides these

---

## 4. Source investigations (honest findings)

| Source | Verdict |
|--------|---------|
| **OpenStreetMap** (operational + lifecycle) | ✅ In use. License-clean (ODbL), building-level. The only open building-level source. |
| **LBNL "Queued Up"** | ❌ GENERATION-only — explicitly excludes loads. Not a data-center source. Keep as a future grid-supply layer. |
| **ISO large-load queues** (ERCOT etc.) | ❌ Aggregate / confidential — no public per-facility geocoded list (e.g. ERCOT ~226 GW in PDFs only). |
| **Baxtel** | ⭐ Richest (8,000+ sites, planned + MW + status). ToS forbids scraping but **sells a license** (free sample + quote). #1 lead. |
| **arXiv 2411.09786** | ⚠️ Has coords+sqft+MW but dataset NOT open — "available via collaboration with authors" (Harvard NSAPH) and derived from Baxtel. Lead, not a download. |
| **SEC 10-Ks** | ⚠️ Metro/market-level only (no building coordinates). Operator/size enrichment, not a geocoded source. Low yield. |
| **Tier-2 directories** (DataCenterMap, Cloudscene, DCD) | ⚠️ ToS restrict bulk extraction → license/permission only. See `docs/TIER2_TOS_REPORT.md`. |

---

## 5. What's left

### Done this session (no blockers)
- ✅ Name-based brand classification (fixed ~85 "unknown" → hyperscale/colocation)
- ✅ GeoJSON output added
- ✅ arXiv + SEC feasibility investigated (findings above)

### Can do next without permission (I can build these)
- **Power-grid context layer (separate layer, not facility rows)** — natural first
  piece is EIA-860 power plants (public, no key). Needs a scoping decision on
  resolution; an EIA API key (free, **your** action) unlocks demand/load series.
- **Forward-geocoding pass** to refine any address-only records to coordinates.
- Optional SEC enrichment (operator/size by metro) — only if we decide metro-level
  size is worth it despite no coordinates.

### Blocked on a decision (biggest gaps)
- **Power capacity (MW) + size (sq ft) + fuller planned coverage** → require a
  **licensed source**. **Baxtel** is the recommended path (covers all three).
- **Repo home** → push to your GitHub or the lab org? Currently local only.

### Not started — the downstream research phase
- Join dataset to natural-hazard layers + power-grid → the actual multi-hazard
  risk assessment (the paper). The dataset is built to make this clean.

---

## 6. Decisions needed (advisor)

1. **Baxtel license** — request the free sample, then decide on cost. This single
   step fills MW + size + most planned coverage. Without it, those fields stay empty.
2. **Repo hosting** — personal GitHub vs lab org (nothing pushed until confirmed).
3. **Coverage target** — current ~1,547 is ~⅓ of the likely true US universe;
   the rest largely requires licensed/commercial sources.

---

## 7. How to run

```bash
cd ~/datacenter-dataset
source .venv/bin/activate
python -m dcdata.pipeline      # rebuilds CSV + GeoPackage + GeoJSON + QA report
pytest                          # 31 tests
```

Outputs in `data/processed/`: `datacenters_all.csv`, `datacenters_conus.csv`,
`datacenters_non_conus.csv`, `datacenters.gpkg`, `datacenters.geojson`,
`data_quality_report.md`, `merge_log.json`.

**Bottom line:** the dataset-engineering machinery is built, tested, and
reproducible. Remaining work is (a) adding sources to raise coverage and fill
**power (MW)** — gated mainly on the **Baxtel licensing decision** — and (b) the
downstream hazard/grid analysis.
