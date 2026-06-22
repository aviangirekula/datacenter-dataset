"""Entity resolution / deduplication.

Merges facilities that refer to the same physical site across sources, using
fuzzy name matching (rapidfuzz) + coordinate proximity (haversine). Rules are
conservative: co-located but differently-named facilities are NOT merged (they
may be distinct buildings on a campus). Every merge is logged for audit, ALL
source observations are preserved, and no record is ever dropped.
"""
from __future__ import annotations

import math
import re
from typing import Optional

from rapidfuzz import fuzz

from dcdata.schema import (
    AreaBasis,
    Confidence,
    CoordinatePrecision,
    Facility,
    FacilityType,
    GeocodePrecision,
    PowerBasis,
    Status,
    make_facility_id,
)

CONF_RANK = {Confidence.high: 3, Confidence.medium: 2, Confidence.low: 1}
PREC_RANK = {
    GeocodePrecision.rooftop: 5,
    GeocodePrecision.parcel: 4,
    GeocodePrecision.address: 3,
    GeocodePrecision.city: 2,
    GeocodePrecision.county: 1,
    GeocodePrecision.unknown: 0,
}
# Prefer building-specific coordinates when merging duplicate observations.
COORD_PREC_RANK = {
    CoordinatePrecision.building: 3,
    CoordinatePrecision.geocoded_address: 2,
    CoordinatePrecision.campus_centroid: 1,
    CoordinatePrecision.unknown: 0,
}
_RANK_TO_CONF = {3: Confidence.high, 2: Confidence.medium, 1: Confidence.low}

# Merge thresholds (tunable; deliberately conservative to protect building-level
# granularity). We only merge near-coincident points; wider cross-source matching
# will be tuned against a real second source.
MERGE_M = 60.0           # max distance to merge ("basically the same point")
LOOSE_NAME_SIM = 80      # min fuzzy name similarity when both names are present
GUARD_BASE_SIM = 85      # min similarity of the non-numeric name parts for the
                         # building-number guard to treat records as distinct
_PREFILTER_DLAT = 0.0015  # ~165 m; skip clearly-distant pairs cheaply
_PREFILTER_DLON = 0.0020

_DIGITS = re.compile(r"\d+")


def differing_building_numbers(a: Optional[str], b: Optional[str]) -> bool:
    """True if two otherwise-similar names differ only by a building/unit number.

    Catches campus siblings like "Portland 2" vs "Portland 3" or "DC1" vs "DC2",
    which must stay distinct. Only fires when the non-numeric parts of the names
    are themselves similar, so unrelated names with numbers aren't affected.
    """
    if not a or not b:
        return False
    nums_a, nums_b = set(_DIGITS.findall(a)), set(_DIGITS.findall(b))
    if not nums_a or not nums_b or nums_a == nums_b:
        return False
    base_a, base_b = _DIGITS.sub("", a).lower(), _DIGITS.sub("", b).lower()
    return fuzz.token_set_ratio(base_a, base_b) >= GUARD_BASE_SIM


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters."""
    radius = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def name_similarity(a: Optional[str], b: Optional[str]) -> Optional[int]:
    """Fuzzy 0-100 name similarity, or None if either name is missing."""
    if not a or not b:
        return None
    return int(fuzz.token_set_ratio(a.lower(), b.lower()))


def is_match(f1: Facility, f2: Facility) -> tuple[bool, Optional[float], Optional[int]]:
    """Return (matched, distance_m, name_sim) for a candidate pair."""
    # cheap bbox prefilter to skip clearly-distant pairs fast
    if abs(f1.latitude - f2.latitude) > _PREFILTER_DLAT or abs(f1.longitude - f2.longitude) > _PREFILTER_DLON:
        return (False, None, None)
    d = haversine_m(f1.latitude, f1.longitude, f2.latitude, f2.longitude)
    if d > MERGE_M:
        return (False, d, None)
    sim = name_similarity(f1.name, f2.name)
    # campus-sibling guard: same name except a differing building number -> distinct
    if differing_building_numbers(f1.name, f2.name):
        return (False, d, sim)
    if sim is None:  # one name missing + near-coincident -> same site
        return (True, d, sim)
    return (sim >= LOOSE_NAME_SIM, d, sim)


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def _ranked(members: list[Facility]) -> list[Facility]:
    """Members sorted by record confidence (highest first)."""
    return sorted(members, key=lambda f: CONF_RANK.get(f.confidence, 0), reverse=True)


def _first(members: list[Facility], attr: str, skip: tuple = ()):
    """First non-null attribute value across members, skipping ``skip`` values."""
    for m in members:
        v = getattr(m, attr)
        if v is not None and v not in skip:
            return v
    return None


def _merge_cluster(members: list[Facility]) -> Facility:
    """Reconcile a cluster of duplicate facilities into one canonical record."""
    if len(members) == 1:
        return members[0]
    ranked = _ranked(members)
    # Prefer the most building-specific coordinate, then finest geocode precision.
    best_coord = max(
        members,
        key=lambda f: (
            COORD_PREC_RANK.get(f.coordinate_precision, 0),
            PREC_RANK.get(f.geocode_precision, 0),
            CONF_RANK.get(f.coord_confidence, 0),
        ),
    )
    name = _first(ranked, "name")

    facility_type = (
        _first(ranked, "facility_type", skip=(FacilityType.unknown, FacilityType.excluded_minor))
        or _first(ranked, "facility_type", skip=(FacilityType.unknown,))
        or FacilityType.unknown
    )

    # preserve ALL source observations (dedupe only byte-identical ones)
    seen: set = set()
    sources = []
    for m in members:
        for s in m.sources:
            key = (s.source_name, s.source_record_id)
            if key not in seen:
                seen.add(key)
                sources.append(s)

    best_rank = max(CONF_RANK.get(m.confidence, 1) for m in members)
    return Facility(
        facility_id=make_facility_id(name, best_coord.latitude, best_coord.longitude),
        name=name,
        operator_company=_first(ranked, "operator_company"),
        facility_type=facility_type,
        status=_first(ranked, "status", skip=(Status.unknown,)) or Status.unknown,
        compute_capabilities=_first(ranked, "compute_capabilities"),
        latitude=best_coord.latitude,
        longitude=best_coord.longitude,
        geom_type=best_coord.geom_type,
        geocode_precision=best_coord.geocode_precision,
        coordinate_precision=best_coord.coordinate_precision,
        coord_confidence=best_coord.coord_confidence,
        address=_first(ranked, "address"),
        city=_first(ranked, "city"),
        state=_first(ranked, "state"),
        county=_first(ranked, "county"),
        zip=_first(ranked, "zip"),
        size_sqft=_first(ranked, "size_sqft"),
        area_basis=_first(ranked, "area_basis", skip=(AreaBasis.unknown,)) or AreaBasis.unknown,
        num_floors=_first(ranked, "num_floors"),
        power_capacity_mw=_first(ranked, "power_capacity_mw"),
        power_basis=_first(ranked, "power_basis", skip=(PowerBasis.unknown,)) or PowerBasis.unknown,
        power_demand_mw=_first(ranked, "power_demand_mw"),
        year_opened=_first(ranked, "year_opened"),
        planned_year=_first(ranked, "planned_year"),
        in_conus=any(m.in_conus for m in members),
        included=any(m.included for m in members),  # if any source calls it real, keep it
        confidence=_RANK_TO_CONF.get(best_rank, Confidence.low),
        notes=_first(ranked, "notes"),
        sources=sources,
        snapshot_date=_first(members, "snapshot_date"),
        dataset_version=_first(members, "dataset_version"),
    )


def _log_entry(canon: Facility, members: list[Facility], idx: list[int], evidence: dict) -> dict:
    pairs = []
    for a in range(len(idx)):
        for b in range(a + 1, len(idx)):
            ev = evidence.get((min(idx[a], idx[b]), max(idx[a], idx[b])))
            if ev is not None:
                dist, sim = ev
                pairs.append({"distance_m": round(dist, 1) if dist is not None else None, "name_sim": sim})
    return {
        "canonical_id": canon.facility_id,
        "n_merged": len(members),
        "members": [
            {
                "facility_id": m.facility_id,
                "name": m.name,
                "sources": [s.source_name for s in m.sources],
                "lat": m.latitude,
                "lon": m.longitude,
            }
            for m in members
        ],
        "evidence": pairs,
    }


def resolve_entities(facilities: list[Facility]) -> tuple[list[Facility], list[dict]]:
    """Resolve duplicates into canonical facilities.

    Returns ``(merged_facilities, merge_log)``. The merge log records each
    multi-member cluster with its members and the distance/name-similarity
    evidence behind the merge, so every decision is auditable.
    """
    n = len(facilities)
    uf = _UnionFind(n)
    evidence: dict[tuple[int, int], tuple] = {}
    for i in range(n):
        for j in range(i + 1, n):
            matched, dist, sim = is_match(facilities[i], facilities[j])
            if matched:
                uf.union(i, j)
                evidence[(i, j)] = (dist, sim)

    clusters: dict[int, list[int]] = {}
    for idx in range(n):
        clusters.setdefault(uf.find(idx), []).append(idx)

    merged: list[Facility] = []
    log: list[dict] = []
    for member_idx in clusters.values():
        members = [facilities[k] for k in member_idx]
        canon = _merge_cluster(members)
        merged.append(canon)
        if len(members) > 1:
            log.append(_log_entry(canon, members, member_idx, evidence))
    return merged, log
