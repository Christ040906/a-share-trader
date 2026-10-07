from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from ashare_realtime_mcp.history_store import SnapshotStore

TZ = ZoneInfo("Asia/Shanghai")

def test_store_roundtrip(tmp_path):
    store = SnapshotStore(str(tmp_path / "x.db"))
    t = datetime(2026,10,8,10,0,tzinfo=TZ)
    cid = store.save_capture(
        t,t.isoformat(),t.isoformat(),
        [{"ts_code":"A.SH","name":"A","last":10,"pre_close":9,"pct_change":11,"amount":1}],
        [{"ts_code":"S.SI","name":"S","close":100,"pre_close":99,"pct_change":1,"amount":1}],
    )
    assert store.latest_capture()["id"] == cid
    assert store.stock_rows(cid)[0]["ts_code"] == "A.SH"
    assert store.nearest_capture(t + timedelta(minutes=3), 10)["id"] == cid


def test_nearest_capture_can_match_provider_source(tmp_path):
    store = SnapshotStore(str(tmp_path / "src.db"))
    t = datetime(2026,10,8,10,0,tzinfo=TZ)
    a = store.save_capture(t,t.isoformat(),t.isoformat(),[],[],"akshare","akshare")
    b = store.save_capture(t + timedelta(minutes=5),t.isoformat(),t.isoformat(),[],[],"tushare","tushare")
    got = store.nearest_capture(t + timedelta(minutes=6), 10, stock_source="akshare", sector_source="akshare")
    assert got["id"] == a
    assert got["id"] != b
