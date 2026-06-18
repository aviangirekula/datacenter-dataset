"""Pluggable geocoder interface.

Default backend is the free US Census geocoder; Nominatim (OSM) is the fallback.
Paid backends (Google/Mapbox) can be added later by implementing this protocol
with no pipeline rewrite. The actual precision achieved is always recorded in
:class:`~dcdata.schema.GeocodePrecision`, regardless of backend.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from dcdata.schema import GeocodePrecision


@dataclass
class GeocodeResult:
    """Outcome of a single geocode call."""

    latitude: float
    longitude: float
    precision: GeocodePrecision
    matched_address: Optional[str] = None
    backend: str = ""


class Geocoder(Protocol):
    """Any geocoder backend implements ``geocode``."""

    name: str

    def geocode(self, address: str) -> Optional[GeocodeResult]:
        """Return a :class:`GeocodeResult`, or ``None`` if unresolved."""
        ...
