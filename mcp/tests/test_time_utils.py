from datetime import datetime
from zoneinfo import ZoneInfo
from ashare_realtime_mcp.time_utils import freshness

TZ = ZoneInfo("Asia/Shanghai")

def test_live():
    now = datetime(2026,10,8,10,0,0,tzinfo=TZ)
    as_of = datetime(2026,10,8,9,59,30,tzinfo=TZ)
    assert freshness(as_of, now)["freshness"] == "LIVE"

def test_stale():
    now = datetime(2026,10,8,10,0,0,tzinfo=TZ)
    as_of = datetime(2026,10,8,9,50,0,tzinfo=TZ)
    assert freshness(as_of, now)["freshness"] == "STALE"

def test_lunch_pause():
    now = datetime(2026,10,8,12,0,0,tzinfo=TZ)
    as_of = datetime(2026,10,8,11,30,0,tzinfo=TZ)
    assert freshness(as_of, now)["freshness"] == "PAUSED"
