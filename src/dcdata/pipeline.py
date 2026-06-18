"""End-to-end pipeline: collect -> classify -> CONUS-tag -> validate -> export.

Run with::

    python -m dcdata.pipeline

Currently wires the OpenStreetMap collector (operational base layer). Additional
collectors are added by enabling them in ``config/sources.yaml`` and registering
them here.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import yaml

from dcdata.collectors.osm import OSMCollector
from dcdata.export import export_dataset, write_quality_report
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

    facilities: list[Facility] = list(OSMCollector(osm_cfg, accessed=snapshot).collect())

    # CONUS tagging (flag, don't drop) + stamp version/snapshot
    for f in facilities:
        f.in_conus = in_conus(f.latitude, f.longitude, f.state)
        f.snapshot_date = snapshot
        f.dataset_version = version

    outdir = root / "data" / "processed"
    stats = export_dataset(facilities, outdir)
    write_quality_report(facilities, outdir / "data_quality_report.md", stats)
    return stats


def main() -> None:
    stats = run()
    print("Pipeline complete. Outputs in data/processed/")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
