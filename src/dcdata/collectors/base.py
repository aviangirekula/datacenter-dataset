"""Base collector interface.

Every source module subclasses :class:`BaseCollector` and yields records in the
common schema, so the pipeline never needs source-specific code. Adding a new
source means adding a module here and registering it in ``config/sources.yaml``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator

from dcdata.schema import Facility


class BaseCollector(ABC):
    """Abstract collector. One subclass per data source.

    Implementations should:
      * read cached raw responses from ``data/raw/`` when present (reproducible),
        otherwise fetch once and cache them;
      * respect each source's rate limits, robots.txt, and licensing;
      * yield fully-formed :class:`Facility` records (pre-resolution), each with
        at least one :class:`~dcdata.schema.FacilitySource` attached.
    """

    #: human-readable source name, also written into provenance
    source_name: str = "base"

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}

    @abstractmethod
    def collect(self) -> Iterator[Facility]:
        """Yield :class:`Facility` records collected from this source."""
        raise NotImplementedError
