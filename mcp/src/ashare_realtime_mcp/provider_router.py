from __future__ import annotations

from .provider import MarketDataProvider, ProviderPayload


class ProviderRouter(MarketDataProvider):
    """Method-level failover router.

    Providers are tried in order. The returned payload keeps the actual provider name,
    and any failed upstream providers are recorded as warnings.
    """

    name = "adaptive"

    def __init__(self, providers: list[MarketDataProvider]):
        if not providers:
            raise RuntimeError("No market-data provider is configured")
        self.providers = providers

    def _route(self, method: str, *args):
        failures = []
        for p in self.providers:
            try:
                payload = getattr(p, method)(*args)
                if not isinstance(payload, ProviderPayload):
                    payload = ProviderPayload(payload, p.name, method)
                data = payload.data
                try:
                    empty = data is None or len(data) == 0
                except TypeError:
                    empty = False
                if empty:
                    raise RuntimeError("empty result")
                if failures:
                    payload.warnings = [*failures, *payload.warnings]
                return payload
            except Exception as exc:
                failures.append(f"{p.name}.{method} failed: {type(exc).__name__}: {str(exc)[:200]}")
        raise RuntimeError(" | ".join(failures))

    def stock_snapshot(self, query: str):
        return self._route("stock_snapshot", query)

    def sector_snapshot(self, query: str | None = None):
        return self._route("sector_snapshot", query)

    def realtime_minutes(self, ts_codes: str, freq: str):
        return self._route("realtime_minutes", ts_codes, freq)

    def intraday_minutes(self, ts_code: str, freq: str):
        return self._route("intraday_minutes", ts_code, freq)

    def l1_sector_classes(self):
        return self._route("l1_sector_classes")

    def sector_members(self, l1_code: str):
        return self._route("sector_members", l1_code)
