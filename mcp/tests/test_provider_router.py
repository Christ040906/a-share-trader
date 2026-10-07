from datetime import datetime
from zoneinfo import ZoneInfo

from ashare_realtime_mcp.provider import MarketDataProvider, ProviderPayload
from ashare_realtime_mcp.provider_router import ProviderRouter

TZ = ZoneInfo("Asia/Shanghai")


class Broken(MarketDataProvider):
    name = "broken"
    def stock_snapshot(self, query): raise RuntimeError("down")
    def sector_snapshot(self, query=None): raise RuntimeError("down")
    def realtime_minutes(self, ts_codes, freq): raise RuntimeError("down")
    def intraday_minutes(self, ts_code, freq): raise RuntimeError("down")
    def l1_sector_classes(self): raise RuntimeError("down")
    def sector_members(self, l1_code): raise RuntimeError("down")


class Good(MarketDataProvider):
    name = "good"
    def stock_snapshot(self, query):
        return ProviderPayload([{"ts_code":"600000.SH","close":10}], self.name, "spot", datetime(2026,10,8,10,0,tzinfo=TZ), "row_timestamp")
    def sector_snapshot(self, query=None): return ProviderPayload([], self.name, "sector")
    def realtime_minutes(self, ts_codes, freq): return ProviderPayload([], self.name, "min")
    def intraday_minutes(self, ts_code, freq): return ProviderPayload([], self.name, "min")
    def l1_sector_classes(self): return ProviderPayload([], self.name, "classes")
    def sector_members(self, l1_code): return ProviderPayload([], self.name, "members")


def test_router_falls_back_and_preserves_actual_source():
    payload = ProviderRouter([Broken(), Good()]).stock_snapshot("600000.SH")
    assert payload.source == "good"
    assert payload.endpoint == "spot"
    assert any("broken.stock_snapshot failed" in x for x in payload.warnings)
