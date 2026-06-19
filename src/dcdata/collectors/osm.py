"""OpenStreetMap collector (Overpass API).

Reads the cached Overpass response from ``data/raw/`` when present (reproducible);
otherwise fetches once and caches it. Emits one :class:`Facility` per OSM element
with OSM provenance attached. OSM is treated as the **operational** base layer —
planned facilities come from interconnection-queue collectors.
"""
from __future__ import annotations

import json
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

OVERPASS_QUERY = """[out:json][timeout:300];
area["ISO3166-1"="US"][admin_level=2]->.us;
(
  nwr["telecom"="data_center"](area.us);
  nwr["man_made"="data_center"](area.us);
  nwr["building"="data_center"](area.us);
);
out center tags;"""

USER_AGENT = "gmu-geoai-dc-dataset/0.1 (research)"


class OSMCollector(BaseCollector):
    """Collect US data centers from OpenStreetMap via the Overpass API."""

    source_name = "OpenStreetMap"
    QUERY = OVERPASS_QUERY  # overridable by subclasses (e.g. lifecycle collector)

    def __init__(self, config: Optional[dict] = None, accessed: Optional[date] = None) -> None:
        super().__init__(config)
        self.overpass_url = self.config.get(
            "overpass_url", "https://overpass-api.de/api/interpreter"
        )
        self.cache = Path(self.config.get("cache", "data/raw/osm/osm_datacenters.json"))
        self._accessed = accessed  # injected for reproducible provenance / tests

    def _load_raw(self) -> dict:
        """Return the raw Overpass JSON, fetching and caching it if needed."""
        if self.cache.exists():
            return json.loads(self.cache.read_text())
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        resp = requests.post(
            self.overpass_url,
            data={"data": self.QUERY},
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=300,
        )
        resp.raise_for_status()
        self.cache.write_text(resp.text)
        return resp.json()

    def collect(self) -> Iterator[Facility]:
        raw = self._load_raw()
        accessed = self._accessed or date.today()
        for el in raw.get("elements", []):
            facility = self._to_facility(el, accessed)
            if facility is not None:
                yield facility

    @staticmethod
    def _coords(el: dict):
        """Return (lat, lon, geom_type, precision, coord_confidence) or None.

        Nodes carry lat/lon directly (placed on a feature -> address-level).
        Ways/relations report a centroid via ``out center`` (a footprint center
        -> parcel-level, higher locational confidence).
        """
        if "lat" in el and "lon" in el:
            return el["lat"], el["lon"], GeomType.point, GeocodePrecision.address, Confidence.medium
        if "center" in el:
            c = el["center"]
            return c["lat"], c["lon"], GeomType.point, GeocodePrecision.parcel, Confidence.high
        return None

    def _status(self, tags: dict) -> Status:
        """Operational by default; lifecycle subclasses override this."""
        return Status.operational

    @staticmethod
    def _address(tags: dict) -> Optional[str]:
        parts = [tags.get("addr:housenumber"), tags.get("addr:street")]
        street = " ".join(p for p in parts if p)
        return street or None

    def _to_facility(self, el: dict, accessed: date) -> Optional[Facility]:
        coords = self._coords(el)
        if coords is None:
            return None
        lat, lon, geom, precision, coord_conf = coords
        tags = el.get("tags", {})
        name = tags.get("name")
        operator = tags.get("operator") or tags.get("brand")
        ftype = classify_facility_type(name, operator, tags)
        included = ftype != FacilityType.excluded_minor

        osm_ref = f"{el.get('type')}/{el.get('id')}"
        source = FacilitySource(
            source_name=self.source_name,
            source_url=f"https://www.openstreetmap.org/{osm_ref}",
            source_record_id=osm_ref,
            date_accessed=accessed,
            confidence=Confidence.high if name else Confidence.medium,
            raw_attributes=tags,
        )

        return Facility(
            facility_id=make_facility_id(name, lat, lon, "osm"),
            name=name,
            operator_company=operator,
            facility_type=ftype,
            status=self._status(tags),
            latitude=lat,
            longitude=lon,
            geom_type=geom,
            geocode_precision=precision,
            coord_confidence=coord_conf,
            address=self._address(tags),
            city=tags.get("addr:city"),
            state=tags.get("addr:state"),
            zip=tags.get("addr:postcode"),
            included=included,
            confidence=Confidence.high if name else Confidence.low,
            notes=(
                None
                if included
                else "Tagged excluded_minor (server room / university / IXP) by classifier."
            ),
            sources=[source],
        )
