"""Facility-type classification from name/operator text.

Reusable across collectors. Conservative by design: only clear minor facilities
(server rooms, university computer rooms, internet exchanges) are tagged
``excluded_minor``; ambiguous records stay ``unknown`` and remain *included* so
we don't silently drop real data centers.
"""
from __future__ import annotations

from typing import Optional

from dcdata.schema import FacilityType

# Substrings (lowercase) that indicate a non-commercial / minor facility.
MINOR_KEYWORDS = (
    "computer room",
    "server room",
    "data closet",
    "internet exchange",
    "telephone exchange",
    "university",
    "college",
)

# Operator names (normalized) for the major hyperscalers.
HYPERSCALE = (
    "amazon web services",
    "amazon",
    "aws",
    "google",
    "meta",
    "facebook",
    "microsoft",
    "apple",
    "oracle",
)

# Operator names (normalized) for major colocation / wholesale providers.
COLOCATION = (
    "digital realty",
    "equinix",
    "coresite",
    "cyrusone",
    "qts",
    "quality technology services",
    "ntt",
    "flexential",
    "switch",
    "databank",
    "stack infrastructure",
    "edgeconnex",
    "aligned",
    "iron mountain",
    "lumen",
    "centersquare",
    "vantage",
    "cologix",
    "tierpoint",
)


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def _match(operator: str, names: tuple[str, ...]) -> bool:
    """True if a known name equals or is contained in the operator string."""
    return any(n == operator or n in operator for n in names)


def classify_facility_type(
    name: Optional[str], operator: Optional[str], tags: Optional[dict] = None
) -> FacilityType:
    """Classify a facility from its name and operator.

    Order matters: minor facilities are screened out first, then hyperscale,
    then colocation; anything else is ``unknown`` (still included).
    """
    blob = f"{_norm(name)} {_norm(operator)}"
    operator_n = _norm(operator)

    if any(kw in blob for kw in MINOR_KEYWORDS):
        return FacilityType.excluded_minor
    if _match(operator_n, HYPERSCALE):
        return FacilityType.hyperscale
    if _match(operator_n, COLOCATION):
        return FacilityType.colocation
    return FacilityType.unknown
