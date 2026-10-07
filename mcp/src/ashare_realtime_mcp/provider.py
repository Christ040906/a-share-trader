from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ProviderPayload:
    data: Any
    source: str
    endpoint: str
    as_of: datetime | None = None
    freshness_basis: str | None = None
    warnings: list[str] = field(default_factory=list)


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    def stock_snapshot(self, query: str) -> ProviderPayload: ...

    @abstractmethod
    def sector_snapshot(self, query: str | None = None) -> ProviderPayload: ...

    @abstractmethod
    def realtime_minutes(self, ts_codes: str, freq: str) -> ProviderPayload: ...

    @abstractmethod
    def intraday_minutes(self, ts_code: str, freq: str) -> ProviderPayload: ...

    @abstractmethod
    def l1_sector_classes(self) -> ProviderPayload: ...

    @abstractmethod
    def sector_members(self, l1_code: str) -> ProviderPayload: ...
