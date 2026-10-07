import sys
from types import SimpleNamespace
import pandas as pd

from ashare_realtime_mcp.akshare_provider import AkShareProvider


def fake_akshare(em_fails=False):
    def em():
        if em_fails:
            raise RuntimeError("em down")
        return pd.DataFrame([
            {"代码":"600000","名称":"浦发银行","最新价":10.2,"涨跌幅":2.0,"成交量":100,"成交额":1000,"最高":10.3,"最低":9.9,"今开":10.0,"昨收":10.0,"涨速":0.2,"5分钟涨跌":0.3,"换手率":1.1,"量比":1.2},
            {"代码":"000001","名称":"平安银行","最新价":11.0,"涨跌幅":1.0,"成交量":200,"成交额":2000,"最高":11.1,"最低":10.7,"今开":10.8,"昨收":10.89,"涨速":0.1,"5分钟涨跌":0.2,"换手率":0.8,"量比":1.0},
        ])
    def idx(**kwargs):
        return pd.DataFrame([{"时间":"2026-10-08 10:01:00","收盘":1}])
    def sina():
        return pd.DataFrame([
            {"代码":"sh600000","名称":"浦发银行","最新价":10.2,"涨跌幅":2.0,"成交量":100,"成交额":1000,"最高":10.3,"最低":9.9,"今开":10.0,"昨收":10.0,"时间戳":"10:01:05"}
        ])
    return SimpleNamespace(
        stock_zh_a_spot_em=em,
        index_zh_a_hist_min_em=idx,
        stock_zh_a_spot=sina,
    )


def test_akshare_em_snapshot_normalizes_and_filters(monkeypatch):
    monkeypatch.setitem(sys.modules, "akshare", fake_akshare(False))
    p = AkShareProvider(retries=0)
    payload = p.stock_snapshot("600000.SH")
    assert payload.source == "akshare"
    assert payload.endpoint == "stock_zh_a_spot_em"
    assert payload.freshness_basis == "benchmark_minute_probe"
    assert len(payload.data) == 1
    row = payload.data[0]
    assert row["ts_code"] == "600000.SH"
    assert row["pct_5m"] == 0.3
    assert row["close"] == 10.2


def test_akshare_falls_back_to_sina(monkeypatch):
    monkeypatch.setitem(sys.modules, "akshare", fake_akshare(True))
    p = AkShareProvider(retries=0)
    payload = p.stock_snapshot("600000.SH")
    assert payload.source == "akshare-sina"
    assert payload.freshness_basis == "row_timestamp"
    assert payload.data[0]["ts_code"] == "600000.SH"
    assert any("Eastmoney spot failed" in x for x in payload.warnings)
