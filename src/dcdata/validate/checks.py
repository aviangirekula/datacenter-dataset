"""Validation and data-quality checks.

CONUS enforcement is *flag, not drop*: a facility outside the contiguous-US
bounding box or in a non-CONUS state is tagged (``in_conus=False``) and routed
to a separate output file so scope can expand later without re-collection.
"""
from __future__ import annotations

# WGS84 bounding box for the contiguous US (excludes AK, HI, territories).
CONUS_MIN_LAT = 24.396308
CONUS_MAX_LAT = 49.384358
CONUS_MIN_LON = -124.848974
CONUS_MAX_LON = -66.885444

NON_CONUS_STATES = {"AK", "HI", "PR", "GU", "VI", "MP", "AS"}

# Plausible facility power range (MW); outside this -> flag for manual review.
MIN_PLAUSIBLE_MW = 0.05
MAX_PLAUSIBLE_MW = 2000.0


def in_conus(lat: float, lon: float, state: str | None = None) -> bool:
    """Return True if the point is inside the CONUS bbox and not a non-CONUS state."""
    if state and state.upper() in NON_CONUS_STATES:
        return False
    return (
        CONUS_MIN_LAT <= lat <= CONUS_MAX_LAT
        and CONUS_MIN_LON <= lon <= CONUS_MAX_LON
    )


def looks_lat_lon_swapped(lat: float, lon: float) -> bool:
    """Heuristic for swapped coordinates.

    US longitudes are large negative; if the value in ``lat`` looks like a US
    longitude and ``lon`` like a US latitude, they were probably swapped.
    """
    return lat < -60 and 20 <= lon <= 50


def power_in_range(mw: float) -> bool:
    """Return True if a MW value is within the plausible facility range."""
    return MIN_PLAUSIBLE_MW <= mw <= MAX_PLAUSIBLE_MW
