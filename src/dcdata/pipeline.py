"""End-to-end pipeline: collect -> classify -> CONUS-tag -> validate -> export.

Run with::

    python -m dcdata.pipeline

Currently wires the OpenStreetMap collector (operational base layer). Additional
collectors are added by enabling them in ``config/sources.yaml`` and registering
them here.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

import yaml

from dcdata.collectors.osm import OSMCollector
from dcdata.collectors.osm_lifecycle import OSMLifecycleCollector
from dcdata.collectors.peeringdb import PeeringDBCollector
from dcdata.collectors.wikidata import WikidataCollector
from dcdata.export import export_dataset, write_quality_report
from dcdata.geocode.reverse import DEFAULT_COUNTY_URL as DEFAULT_TIGER_URL
from dcdata.geocode.reverse import TigerReverseGeocoder
from dcdata.resolve.dedup import resolve_entities
from dcdata.schema import Facility
from dcdata.validate.checks import in_conus

# repo root = three levels up from this file (src/dcdata/pipeline.py)
ROOT = Path(__file__).resolve().parents[2]


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def run(root: Path = ROOT, accessed: Optional[date] = None) -> dict:
    """Run the full pipeline and write outputs to ``data/processed/``."""
    settings = _load_yaml(root / "config" / "settings.yaml")
    sources = _load_yaml(root / "config" / "sources.yaml")
    version = settings["dataset"]["version"]
    snapshot = accessed or date.today()

    osm_cfg = dict(sources["osm"])
    osm_cfg["cache"] = str(root / osm_cfg["cache"])  # resolve cache path against repo root

    # Operational base layer (OSM) + planned/under-construction layer (OSM lifecycle).
    collected: list[Facility] = list(OSMCollector(osm_cfg, accessed=snapshot).collect())
    n_operational = len(collected)

    life_cfg = dict(sources.get("osm_lifecycle", {}))
    life_cfg.setdefault("overpass_url", osm_cfg.get("overpass_url"))
    life_cfg["cache"] = str(root / life_cfg.get("cache", "data/raw/osm/osm_datacenters_lifecycle.json"))
    collected += list(OSMLifecycleCollector(life_cfg, accessed=snapshot).collect())
    n_lifecycle = len(collected) - n_operational

    # PeeringDB (colocation/interconnection) + Wikidata (CC0) coverage layers.
    pdb_cfg = dict(sources.get("peeringdb", {}))
    pdb_cfg["cache"] = str(root / pdb_cfg.get("cache", "data/raw/peeringdb/fac_us.json"))
    before = len(collected)
    collected += list(PeeringDBCollector(pdb_cfg, accessed=snapshot).collect())
    n_peeringdb = len(collected) - before

    wd_cfg = dict(sources.get("wikidata", {}))
    wd_cfg["cache"] = str(root / wd_cfg.get("cache", "data/raw/wikidata/datacenters_us.json"))
    before = len(collected)
    collected += list(WikidataCollector(wd_cfg, accessed=snapshot).collect())
    n_wikidata = len(collected) - before

    # Entity resolution: merge duplicate facilities across (and within) sources.
    facilities, merge_log = resolve_entities(collected)

    # Reverse-geocode coordinates -> state/county via Census TIGER (public domain).
    tiger_cfg = settings.get("tiger", {})
    reverse_geocoder = TigerReverseGeocoder(
        county_url=tiger_cfg.get("county_url", DEFAULT_TIGER_URL),
        cache_dir=str(root / tiger_cfg.get("cache_dir", "data/raw/tiger")),
    )
    print("Reverse-geocoding via Census TIGER county shapefile (downloads/caches to data/raw/tiger/)...")
    geo_stats = reverse_geocoder.assign(facilities)

    # CONUS tagging (flag, don't drop) using the authoritative state + stamp version
    for f in facilities:
        f.in_conus = in_conus(f.latitude, f.longitude, f.state)
        f.snapshot_date = snapshot
        f.dataset_version = version

    outdir = root / "data" / "processed"
    stats = export_dataset(facilities, outdir)
    (outdir / "merge_log.json").write_text(json.dumps(merge_log, indent=2, default=str))
    stats["collected_pre_resolve"] = len(collected)
    stats["osm_operational"] = n_operational
    stats["osm_lifecycle_planned"] = n_lifecycle
    stats["peeringdb"] = n_peeringdb
    stats["wikidata"] = n_wikidata
    stats["merged_clusters"] = len(merge_log)
    stats.update(geo_stats)
    write_quality_report(facilities, outdir / "data_quality_report.md", stats)
    return stats


def main() -> None:
    stats = run()
    print("Pipeline complete. Outputs in data/processed/")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
