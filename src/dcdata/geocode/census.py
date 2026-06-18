"""US Census geocoder backend (free, no API key).

Default backend. Resolves US street addresses to coordinates via the Census
Geocoding Services API. Census returns address-interpolated points (not true
rooftop), so precision is recorded as ``address``.
"""
from __future__ import annotations

from typing import Optional

import requests

from dcdata.geocode.base import GeocodeResult
from dcdata.schema import GeocodePrecision

_ENDPOINT = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"


class CensusGeocoder:
    """Geocode US street addresses using the free Census API."""

    name = "census"

    def __init__(self, timeout: float = 20.0, benchmark: str = "Public_AR_Current") -> None:
        self.timeout = timeout
        self.benchmark = benchmark

    def geocode(self, address: str) -> Optional[GeocodeResult]:
        """Return a :class:`GeocodeResult`, or ``None`` if unmatched."""
        params = {"address": address, "benchmark": self.benchmark, "format": "json"}
        resp = requests.get(_ENDPOINT, params=params, timeout=self.timeout)
        resp.raise_for_status()
        matches = resp.json().get("result", {}).get("addressMatches", [])
        if not matches:
            return None
        m = matches[0]
        coords = m["coordinates"]  # x = longitude, y = latitude
        return GeocodeResult(
            latitude=coords["y"],
            longitude=coords["x"],
            precision=GeocodePrecision.address,
            matched_address=m.get("matchedAddress"),
            backend=self.name,
        )
