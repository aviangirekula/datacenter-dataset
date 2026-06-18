"""Core data schema for the US data center dataset.

Defines the canonical record shape every collector must emit, plus the
normalized provenance model. A single resolved facility (:class:`Facility`)
may carry many source observations (:class:`FacilitySource`) after entity
resolution; all source URLs are preserved (project requirement #5).
"""
from __future__ import annotations

import hashlib
from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class FacilityType(str, Enum):
    traditional = "traditional"
    hyperscale = "hyperscale"
    colocation = "colocation"
    ai_compute = "ai_compute"
    enterprise = "enterprise"
    edge = "edge"
    excluded_minor = "excluded_minor"  # server rooms, university computer rooms, IXPs
    unknown = "unknown"


class Status(str, Enum):
    operational = "operational"
    under_construction = "under_construction"
    planned = "planned"
    decommissioned = "decommissioned"
    unknown = "unknown"


class GeocodePrecision(str, Enum):
    rooftop = "rooftop"
    parcel = "parcel"
    address = "address"
    city = "city"
    county = "county"
    unknown = "unknown"


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class AreaBasis(str, Enum):
    """What ``size_sqft`` measures (sources mix these)."""
    gross_building = "gross_building"
    white_space = "white_space"
    unknown = "unknown"


class PowerBasis(str, Enum):
    """What ``power_capacity_mw`` measures (IT load vs. total facility power)."""
    it_load = "it_load"
    total_facility = "total_facility"
    unknown = "unknown"


class GeomType(str, Enum):
    point = "point"
    polygon = "polygon"


class FacilitySource(BaseModel):
    """One observation of a facility from a single source.

    Many of these attach to one resolved :class:`Facility`, preserving every
    source URL and the raw attributes exactly as collected (for audit/debug).
    """

    source_name: str
    source_url: Optional[str] = None
    source_record_id: Optional[str] = None
    date_accessed: date
    confidence: Confidence = Confidence.medium
    raw_attributes: dict = Field(default_factory=dict)


class Facility(BaseModel):
    """A single data center facility (building or campus).

    This is the canonical record. Collectors emit pre-resolution instances;
    entity resolution merges duplicates into one instance whose ``sources``
    list holds every contributing observation.
    """

    facility_id: str
    campus_id: Optional[str] = None  # groups buildings into a campus

    name: Optional[str] = None
    operator_company: Optional[str] = None
    facility_type: FacilityType = FacilityType.unknown
    status: Status = Status.unknown

    # --- location ---
    latitude: float
    longitude: float
    geom_type: GeomType = GeomType.point
    geocode_precision: GeocodePrecision = GeocodePrecision.unknown
    coord_confidence: Confidence = Confidence.medium  # confidence in LOCATION specifically

    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    county: Optional[str] = None
    zip: Optional[str] = None
    country: str = "US"

    # --- size & power (basis enums because sources disagree on definitions) ---
    size_sqft: Optional[float] = None
    area_basis: AreaBasis = AreaBasis.unknown
    power_capacity_mw: Optional[float] = None
    power_basis: PowerBasis = PowerBasis.unknown
    power_demand_mw: Optional[float] = None  # "entry demand" per advisor

    year_opened: Optional[int] = None
    planned_year: Optional[int] = None

    # --- scope / curation flags (tag, don't drop) ---
    in_conus: bool = True
    included: bool = True  # curated-view flag; False for excluded_minor / non-CONUS
    confidence: Confidence = Confidence.medium  # record-level identity confidence
    notes: Optional[str] = None

    # --- provenance & versioning ---
    sources: list[FacilitySource] = Field(default_factory=list)
    snapshot_date: Optional[date] = None
    dataset_version: Optional[str] = None

    @field_validator("latitude")
    @classmethod
    def _lat_range(cls, v: float) -> float:
        if not -90 <= v <= 90:
            raise ValueError(f"latitude out of range: {v}")
        return v

    @field_validator("longitude")
    @classmethod
    def _lon_range(cls, v: float) -> float:
        if not -180 <= v <= 180:
            raise ValueError(f"longitude out of range: {v}")
        return v

    @field_validator("state")
    @classmethod
    def _state_upper(cls, v: Optional[str]) -> Optional[str]:
        return v.upper() if v else v


def make_facility_id(name: Optional[str], lat: float, lon: float, source: str = "") -> str:
    """Return a deterministic short ID from normalized name + rounded coords.

    Stable across runs so re-collection doesn't churn IDs. Coordinates are
    rounded to 5 decimals (~1.1 m) so trivial precision differences collapse to
    the same ID. ``source`` is included for pre-resolution IDs; the merged
    canonical facility is re-keyed without it during entity resolution.
    """
    key = f"{(name or '').strip().lower()}|{round(lat, 5)}|{round(lon, 5)}|{source}"
    return "dc_" + hashlib.sha1(key.encode()).hexdigest()[:12]
