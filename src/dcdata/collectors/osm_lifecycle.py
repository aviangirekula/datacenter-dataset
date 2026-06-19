"""OSM lifecycle collector — planned / under-construction data centers.

Uses OpenStreetMap lifecycle tags (``construction=data_center``,
``proposed:*=data_center``) to capture the buildout pipeline at building level.
Coverage is limited (few mappers tag planned sites), but every record is
license-clean (ODbL) and traceable — exactly the trade-off chosen for planned
facilities. Reuses all of :class:`OSMCollector`'s parsing; only the query and
status differ.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from dcdata.collectors.osm import OSMCollector
from dcdata.schema import Status

LIFECYCLE_QUERY = """[out:json][timeout:280];
area["ISO3166-1"="US"][admin_level=2]->.us;
(
  nwr["construction"="data_center"](area.us);
  nwr["proposed:man_made"="data_center"](area.us);
  nwr["proposed:telecom"="data_center"](area.us);
  nwr["proposed"="data_center"](area.us);
);
out center tags;"""


class OSMLifecycleCollector(OSMCollector):
    """Collect planned / under-construction data centers from OSM lifecycle tags."""

    source_name = "OpenStreetMap"
    QUERY = LIFECYCLE_QUERY

    def __init__(self, config: Optional[dict] = None, accessed=None) -> None:
        super().__init__(config, accessed)
        if not (config or {}).get("cache"):
            self.cache = Path("data/raw/osm/osm_datacenters_lifecycle.json")

    def _status(self, tags: dict) -> Status:
        """``proposed:*`` -> planned; ``construction*`` -> under_construction."""
        if any(k == "proposed" or k.startswith("proposed:") for k in tags):
            return Status.planned
        return Status.under_construction
