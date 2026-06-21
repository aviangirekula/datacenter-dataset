"""PeeringDB collector — colocation / interconnection facilities.

PeeringDB is an open, community-maintained database of network facilities
(many of which are colocation data centers). The public REST API returns US
facilities with names and coordinates. Cached on first fetch for reproducibility.

License note: PeeringDB exposes a public API intended for programmatic use;
verify redistribution terms before bulk republication (flagged in SOURCES.md).
"""
from __future__ import annotations

import json
import os
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

API_URL = "https://www.peeringdb.com/api/fac?country=US"
USER_AGENT = "gmu-geoai-dc-dataset/0.1 (research)"


class PeeringDBCollector(BaseCollector):
    """Collect US colocation/interconnection facilities from PeeringDB."""

    source_name = "PeeringDB"

    def __init__(self, config: Optional[dict] = None, accessed: Optional[date] = None) -> None:
        super().__init__(config)
        self.api_url = self.config.get("api_url", API_URL)
        self.cache = Path(self.config.get("cache", "data/raw/peeringdb/fac_us.json"))
        self._accessed = accessed

    def _load_raw(self) -> dict:
        # Use a cached response only if it's real data (not a throttle/error blob).
        if self.cache.exists():
            cached = json.loads(self.cache.read_text())
            if "data" in cached:
                return cached
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        headers = {"User-Agent": USER_AGENT}
        api_key = os.environ.get("PEERINGDB_API_KEY")
        if api_key:  # optional: higher rate limits, no account-less throttling
            headers["Authorization"] = f"Api-Key {api_key}"
        try:
            resp = requests.get(self.api_url, headers=headers, timeout=120)
        except requests.RequestException as exc:
            print(f"  [PeeringDB] fetch failed ({exc}); skipping this source.")
            return {"data": []}
        if resp.status_code != 200 or '"data"' not in resp.text:
            print(
                f"  [PeeringDB] unavailable (HTTP {resp.status_code}); skipping. "
                "Likely anonymous rate-limit — retry later or set PEERINGDB_API_KEY."
            )
            return {"data": []}
        self.cache.write_text(resp.text)
        return resp.json()

    def collect(self) -> Iterator[Facility]:
        raw = self._load_raw()
        accessed = self._accessed or date.today()
        for rec in raw.get("data", []):
            facility = self._to_facility(rec, accessed)
            if facility is not None:
                yield facility

    def _to_facility(self, rec: dict, accessed: date) -> Optional[Facility]:
        lat, lon = rec.get("latitude"), rec.get("longitude")
        if lat in (None, "") or lon in (None, ""):
            return None  # PeeringDB has some coordinate-less facilities; skip (could geocode later)
        name = rec.get("name")
        ftype = classify_facility_type(name, None)
        included = ftype != FacilityType.excluded_minor
        rec_id = str(rec.get("id"))
        source = FacilitySource(
            source_name=self.source_name,
            source_url=f"https://www.peeringdb.com/fac/{rec_id}",
            source_record_id=rec_id,
            date_accessed=accessed,
            confidence=Confidence.high if name else Confidence.medium,
            raw_attributes={
                k: rec.get(k)
                for k in ("name", "city", "state", "zipcode", "address1", "org_id", "campus_id")
            },
        )
        return Facility(
            facility_id=make_facility_id(name, float(lat), float(lon), "peeringdb"),
            name=name,
            facility_type=ftype,
            status=Status.operational,
            latitude=float(lat),
            longitude=float(lon),
            geom_type=GeomType.point,
            geocode_precision=GeocodePrecision.address,  # PeeringDB geocodes addresses
            coord_confidence=Confidence.medium,
            address=rec.get("address1") or None,
            city=rec.get("city") or None,
            state=rec.get("state") or None,
            zip=rec.get("zipcode") or None,
            included=included,
            confidence=Confidence.high if name else Confidence.medium,
            notes=None if included else "Tagged excluded_minor by classifier.",
            sources=[source],
        )
