from __future__ import annotations

from .provider import MarketDataProvider, ProviderPayload


class TushareProvider(MarketDataProvider):
    name = "tushare"

    def __init__(self, token: str):
        if not token:
            raise RuntimeError("TUSHARE_TOKEN is not configured")
        try:
            import tushare as ts
        except ImportError as exc:
            raise RuntimeError("tushare package is not installed") from exc
        ts.set_token(token)
        self.pro = ts.pro_api()

    def stock_snapshot(self, query: str):
        fields = "ts_code,name,pre_close,high,open,low,close,vol,amount,num,trade_time"
        return ProviderPayload(self.pro.rt_k(ts_code=query, fields=fields), self.name, "rt_k", freshness_basis="row_timestamp")

    def sector_snapshot(self, query: str | None = None):
        data = self.pro.rt_sw_k(ts_code=query) if query else self.pro.rt_sw_k()
        return ProviderPayload(data, self.name, "rt_sw_k", freshness_basis="row_timestamp")

    def realtime_minutes(self, ts_codes: str, freq: str):
        return ProviderPayload(self.pro.rt_min(ts_code=ts_codes, freq=freq), self.name, "rt_min", freshness_basis="bar_timestamp")

    def intraday_minutes(self, ts_code: str, freq: str):
        return ProviderPayload(self.pro.rt_min_daily(ts_code=ts_code, freq=freq), self.name, "rt_min_daily", freshness_basis="bar_timestamp")

    def l1_sector_classes(self):
        return ProviderPayload(self.pro.index_classify(level="L1", src="SW2021"), self.name, "index_classify", freshness_basis="reference_data")

    def sector_members(self, l1_code: str):
        return ProviderPayload(self.pro.index_member_all(l1_code=l1_code, is_new="Y"), self.name, "index_member_all", freshness_basis="reference_data")
