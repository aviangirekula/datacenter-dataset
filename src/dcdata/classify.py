"""Facility-type classification from name/operator text.

Reusable across collectors. Conservative by design: only clear minor facilities
(server rooms, university computer rooms, internet exchanges) are tagged
``excluded_minor``; ambiguous records stay ``unknown`` and remain *included* so
we don't silently drop real data centers.
"""
from __future__ import annotations

import re
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


def _brand_in_name(name: str, brands: tuple[str, ...]) -> bool:
    """True if a brand appears as a whole word/phrase in the name.

    Word-boundary matching avoids false positives (e.g. ``meta`` won't match
    ``Metairie``). Used only as a fallback when the ``operator`` tag is missing,
    which is common for OSM under-construction entries like ``Google datacenter``.
    """
    if not name:
        return False
    return any(re.search(rf"\b{re.escape(b)}\b", name) for b in brands)


def classify_facility_type(
    name: Optional[str], operator: Optional[str], tags: Optional[dict] = None
) -> FacilityType:
    """Classify a facility from its name and operator.

    Order matters: minor facilities are screened out first, then operator-based
    matches (strong signal), then a conservative name-based brand fallback;
    anything else is ``unknown`` (still included).
    """
    blob = f"{_norm(name)} {_norm(operator)}"
    operator_n = _norm(operator)
    name_n = _norm(name)

    if any(kw in blob for kw in MINOR_KEYWORDS):
        return FacilityType.excluded_minor
    if _match(operator_n, HYPERSCALE):
        return FacilityType.hyperscale
    if _match(operator_n, COLOCATION):
        return FacilityType.colocation
    # fallback: brand named in the facility name but no operator tag
    if _brand_in_name(name_n, HYPERSCALE):
        return FacilityType.hyperscale
    if _brand_in_name(name_n, COLOCATION):
        return FacilityType.colocation
    return FacilityType.unknown
