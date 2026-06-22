"""Manual curation collector — hand-curated building-specific records/attributes.

Lets a researcher layer in building-level facilities and attributes (precise
coordinates, floors, status, compute capabilities, energy) that the automated
APIs miss. Each curated row carries the same provenance as every other source
(source URL + confidence) and flows through the SAME dedup/validation pipeline:

  * a curated row at a NEW location becomes a new facility;
  * a curated row at an EXISTING facility's location merges into it, and because
    curated rows default to high confidence, their attributes win during
    reconciliation — so this doubles as an attribute-override path.

Edit ``data/manual/curated_facilities.csv`` to add rows. See docs/MANUAL_CURATION.md.
"""
from __future__ import annotations

import csv
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Optional

from dcdata.collectors.base import BaseCollector
from dcdata.schema import (
    Confidence,
    CoordinatePrecision,
    Facility,
    FacilitySource,
    FacilityType,
    Status,
    make_facility_id,
)

EXAMPLE_MARKER = "__EXAMPLE__"  # rows whose name is this are skipped (template guidance)


def _s(row: dict, key: str) -> Optional[str]:
    v = (row.get(key) or "").strip()
    return v or None


def _num(row: dict, key: str) -> Optional[float]:
    v = _s(row, key)
    try:
        return float(v) if v is not None else None
    except ValueError:
        return None


def _int(row: dict, key: str) -> Optional[int]:
    v = _s(row, key)
    try:
        return int(float(v)) if v is not None else None
    except ValueError:
        return None


def _enum(value: Optional[str], enum_cls, default):
    if not value:
        return default
    try:
        return enum_cls(value.strip().lower())
    except ValueError:
        return default


class ManualCurationCollector(BaseCollector):
    """Collect hand-curated facility records from a researcher-maintained CSV."""

    source_name = "Manual curation"

    def __init__(self, config: Optional[dict] = None, accessed: Optional[date] = None) -> None:
        super().__init__(config)
        self.path = Path(self.config.get("path", "data/manual/curated_facilities.csv"))
        self._accessed = accessed

    def collect(self) -> Iterator[Facility]:
        if not self.path.exists():
            return
        accessed = self._accessed or date.today()
        with self.path.open(newline="") as fh:
            for row in csv.DictReader(fh):
                facility = self._to_facility(row, accessed)
                if facility is not None:
                    yield facility

    def _to_facility(self, row: dict, accessed: date) -> Optional[Facility]:
        name = _s(row, "name")
        if not name or name == EXAMPLE_MARKER:
            return None  # skip blank rows and the template example
        try:
            lat, lon = float(row["latitude"]), float(row["longitude"])
        except (KeyError, ValueError, TypeError):
            return None  # a curated record must have coordinates
        conf = _enum(_s(row, "confidence"), Confidence, Confidence.high)
        rec_id = _s(row, "record_id") or name
        source = FacilitySource(
            source_name=self.source_name,
            source_url=_s(row, "source_url"),
            source_record_id=rec_id,
            date_accessed=accessed,
            confidence=conf,
            raw_attributes={k: v for k, v in row.items() if v},
        )
        return Facility(
            facility_id=make_facility_id(name, lat, lon, "manual"),
            name=name,
            operator_company=_s(row, "operator_company"),
            facility_type=_enum(_s(row, "facility_type"), FacilityType, FacilityType.unknown),
            status=_enum(_s(row, "status"), Status, Status.unknown),
            compute_capabilities=_s(row, "compute_capabilities"),
            latitude=lat,
            longitude=lon,
            coordinate_precision=_enum(
                _s(row, "coordinate_precision"), CoordinatePrecision, CoordinatePrecision.building
            ),
            coord_confidence=conf,
            address=_s(row, "address"),
            city=_s(row, "city"),
            state=_s(row, "state"),
            zip=_s(row, "zip"),
            size_sqft=_num(row, "size_sqft"),
            num_floors=_int(row, "num_floors"),
            power_demand_mw=_num(row, "power_demand_mw"),
            included=True,
            confidence=conf,
            notes=_s(row, "notes"),
            sources=[source],
        )
