"""Wikidata collector — US data centers via SPARQL.

Queries Wikidata (data center = Q671224) for US facilities with coordinates.
Low volume (~12) and coordinate precision varies, so records come in at low
coord-confidence — dedup prefers OSM/PeeringDB coordinates when they overlap.
Data is CC0 (public domain).
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Optional

import requests

from dcdata.classify import classify_facility_type
from dcdata.collectors.base import BaseCollector
from dcdata.schema import (
    Confidence,
    Facility,
    FacilitySource,
    FacilityType,
    GeocodePrecision,
    GeomType,
    Status,
    make_facility_id,
)

SPARQL_URL = "https://query.wikidata.org/sparql"
QUERY = """SELECT ?dc ?dcLabel ?coord ?operatorLabel WHERE {
  ?dc wdt:P31/wdt:P279* wd:Q671224 .
  ?dc wdt:P17 wd:Q30 .
  ?dc wdt:P625 ?coord .
  OPTIONAL { ?dc wdt:P137 ?operator. }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}"""
USER_AGENT = "gmu-geoai-dc-dataset/0.1 (research)"
_POINT = re.compile(r"Point\(([-\d.]+) ([-\d.]+)\)")


class WikidataCollector(BaseCollector):
    """Collect US data centers from Wikidata via SPARQL."""

    source_name = "Wikidata"

    def __init__(self, config: Optional[dict] = None, accessed: Optional[date] = None) -> None:
        super().__init__(config)
        self.sparql_url = self.config.get("sparql_url", SPARQL_URL)
        self.cache = Path(self.config.get("cache", "data/raw/wikidata/datacenters_us.json"))
        self._accessed = accessed

    def _load_raw(self) -> dict:
        if self.cache.exists():
            return json.loads(self.cache.read_text())
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(
            self.sparql_url,
            params={"query": QUERY, "format": "json"},
            headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
            timeout=120,
        )
        resp.raise_for_status()
        self.cache.write_text(resp.text)
        return resp.json()

    @staticmethod
    def parse_point(wkt: str) -> Optional[tuple[float, float]]:
        """Parse a WKT 'Point(lon lat)' into (lat, lon)."""
        m = _POINT.match(wkt)
        if not m:
            return None
        lon, lat = float(m.group(1)), float(m.group(2))
        return lat, lon

    def collect(self) -> Iterator[Facility]:
        raw = self._load_raw()
        accessed = self._accessed or date.today()
        for b in raw.get("results", {}).get("bindings", []):
            facility = self._to_facility(b, accessed)
            if facility is not None:
                yield facility

    def _to_facility(self, b: dict, accessed: date) -> Optional[Facility]:
        point = self.parse_point(b["coord"]["value"])
        if point is None:
            return None
        lat, lon = point
        qid = b["dc"]["value"].split("/")[-1]
        name = b.get("dcLabel", {}).get("value")
        operator = b.get("operatorLabel", {}).get("value")
        ftype = classify_facility_type(name, operator)
        included = ftype != FacilityType.excluded_minor
        source = FacilitySource(
            source_name=self.source_name,
            source_url=f"https://www.wikidata.org/wiki/{qid}",
            source_record_id=qid,
            date_accessed=accessed,
            confidence=Confidence.medium,
            raw_attributes={"label": name, "operator": operator},
        )
        return Facility(
            facility_id=make_facility_id(name, lat, lon, "wikidata"),
            name=name,
            operator_company=operator,
            facility_type=ftype,
            status=Status.operational,
            latitude=lat,
            longitude=lon,
            geom_type=GeomType.point,
            geocode_precision=GeocodePrecision.unknown,  # Wikidata coord precision varies
            coord_confidence=Confidence.low,
            included=included,
            confidence=Confidence.medium if name else Confidence.low,
            notes=None if included else "Tagged excluded_minor by classifier.",
            sources=[source],
        )
