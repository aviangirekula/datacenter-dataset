# Tier-2 Commercial Directory — ToS & Licensing Report

**Purpose:** assess which commercial data-center directories would meaningfully
improve coverage and what their terms/licensing require.

**Method:** fetched `robots.txt` and Terms pages where accessible; supplemented
with public descriptions. Findings are marked *verified* (read directly) or
*unconfirmed* (not retrievable / needs direct review).

## Key principle (read first)

`robots.txt` governs **crawling for search indexing** — it does **not** grant
rights to extract, store, or redistribute data. Directory contents are typically
protected by Terms of Service plus database/compilation rights. A permissive
`robots.txt` and a scraping-prohibition in the ToS routinely coexist (see Baxtel
below). The compliant path to bulk data is a **license / API / written
permission**, not scraping.

## Findings by source

### 1. Baxtel — highest-value lead ⭐
- **Coverage:** 8,000+ facilities across 600 regions; tracks operational **plus
  40.5 GW under-construction and 238 GW planned**. Fields: location, company,
  region, operational **status**, and **power capacity (current and planned)**.
  This directly fills our two biggest gaps (planned facilities + MW).
- **robots.txt** *(verified):* listing pages crawlable for SEO; blocks
  `/admin`, `/api`, `/users`, `/search`.
- **ToS** *(verified):* **explicitly prohibits** "data scraping or data mining";
  no "copy, reproduce, modify, distribute, or create derivative works"; license
  is "personal or internal business use only"; no building a competitive product.
  Public non-proprietary facts may be cited in research **with attribution +
  backlinks**; gated content needs written permission.
- **Compliant path** *(verified):* Baxtel **sells a dataset license** —
  one-time snapshot or annual subscription; "request a sample dataset" + quote,
  ~1 business-day response. No academic price published (worth asking).
- **Recommendation:** **pursue a sample + quote through the lab.** This is the
  single change that would most improve the dataset, and licensing is the only
  compliant route given the ToS.

### 2. arXiv 2411.09786 — possible open academic dataset
- "Environmental Burden of US Data Centers in the AI Era" reportedly built a
  ~1,182-facility US dataset (provider, address, lat/lon, sqft), partly via
  scraping datacenters.com.
- **Status** *(unconfirmed):* the abstract has no data-availability statement;
  the full paper / supplementary may release it (check for Zenodo/GitHub).
- **Recommendation:** check the full text; if openly licensed, it's a low-effort,
  citable, license-clean cross-reference (and a methodology comparison point).

### 3. DataCenterMap
- **Coverage:** large, long-standing directory (operator, location).
- **robots.txt** *(unconfirmed):* returned HTTP 429 (rate-limited) — not read.
- **ToS** *(unconfirmed):* a Terms of Use page exists; not retrieved. Needs
  direct review before any use.
- **Recommendation:** moderate value; review ToS, treat as license/permission
  only. Lower priority than Baxtel.

### 4. Cloudscene (Megaport)
- **Coverage:** colocation + cloud-provider directory.
- **robots.txt** *(verified):* fully crawlable (`Allow: /`, data-center sitemap).
- **ToS** *(partially verified):* at `explore.cloudscene.com/terms-of-service/`;
  grants a "temporary, limited licence to access and use (but not modify)… for
  personal, non-transitory viewing" — i.e., bulk extraction/redistribution not
  permitted. Full terms need a direct read.
- **Recommendation:** review ToS; license/permission only. Lower priority.

### 5. Data Center Dynamics (DCD)
- **Coverage:** news + a database; useful mainly for **planned-facility
  announcements**, not bulk structured data.
- **robots.txt** *(verified):* general crawlers allowed, but **AI bots blocked**
  (ClaudeBot, GPTBot, etc.) and `Content-Signal: ai-train=no`.
- **ToS** *(unconfirmed):* not retrieved.
- **Recommendation:** manual reference for planned news; not a bulk source.

## Bottom line

| Source | Coverage gain | Compliant access | Priority |
|---|---|---|---|
| **Baxtel** | **High** (planned + MW + status + location) | **License** (sample+quote) | **1 — pursue via lab** |
| arXiv 2411.09786 | Medium (coords + sqft, ~1.2k) | Open if released | 2 — check availability |
| DataCenterMap | Medium | ToS review → license | 3 |
| Cloudscene | Medium | ToS review → license | 3 |
| DCD | Low (news) | Manual reference | 4 |
