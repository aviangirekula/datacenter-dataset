# Manual Curation Workflow

Automated sources miss building-level detail — exact building coordinates, floor
counts, compute capabilities, and confirmed status. This workflow lets you layer
in hand-curated records and attributes **with the same provenance and confidence
tracking as every other source**, fully reproducibly.

## How it works

1. Edit **`data/manual/curated_facilities.csv`** — one row per building.
2. Re-run the pipeline (`python -m dcdata.pipeline`).
3. Each curated row flows through the same dedup + validation + export as every
   other source.

Because curated rows default to **`confidence = high`**, they behave two ways:

- **New building** → a curated row at a new location becomes a new facility.
- **Attribute override / enrichment** → a curated row placed at an *existing*
  facility's coordinates merges into it (dedup matches by name + proximity), and
  its high-confidence attributes (floors, status, compute, precise coordinates)
  win during reconciliation — while **all** source URLs are still preserved.

## Columns

| column | required | notes |
|---|---|---|
| `name` | ✅ | facility/building name |
| `latitude`, `longitude` | ✅ | building-specific coordinates (WGS84) |
| `coordinate_precision` | – | `building` (default) / `campus_centroid` / `geocoded_address` |
| `operator_company` | – | owner/operator |
| `facility_type` | – | `hyperscale` / `colocation` / `ai_compute` / `traditional` / … |
| `status` | – | `operational` / `under_construction` / `planned` |
| `compute_capabilities` | – | free text, e.g. `AI/GPU`, `HPC`, `traditional` |
| `address`, `city`, `state`, `zip` | – | state/county are re-derived from coordinates anyway |
| `num_floors` | – | storeys (feeds the modeled energy estimate) |
| `size_sqft` | – | per-floor footprint |
| `power_demand_mw` | – | only if you have a real/sourced figure |
| `confidence` | – | `high` (default) / `medium` / `low` |
| `source_url` | – | **strongly recommended** — the article/filing the fact came from |
| `record_id` | – | optional stable id for the curated row |
| `notes` | – | anything worth recording |

## Rules

- Keep the header row. Delete the `__EXAMPLE__` row (it is skipped automatically).
- Only `name`, `latitude`, `longitude` are required; leave unknown fields blank.
- Always add a `source_url` for traceability — this is curated data, so its
  provenance matters most.
- Do **not** paste in data from sources whose terms prohibit redistribution
  (e.g. commercial directories). Cite a public article/filing instead.

## Optional: LLM-assisted extraction (inspiration)

For attributes buried in unstructured news/industry articles (floors, MW,
status), an LLM-assisted "news → structured row" step (cf. Google's *Groundsource*)
can draft rows for this CSV — but a human should verify each row and its
`source_url` before it lands here.
