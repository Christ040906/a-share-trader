from ashare_realtime_mcp.analytics import pct_change, neutral_prefilter


def test_pct_change():
    assert pct_change(11, 10) == 10.0


def test_prefilter_constraints_and_st():
    rows = [
        {"ts_code":"600001.SH","name":"A","close":10,"pre_close":9,"amount":100},
        {"ts_code":"300001.SZ","name":"B","close":10,"pre_close":10,"amount":200},
        {"ts_code":"600002.SH","name":"ST C","close":5,"pre_close":5,"amount":300},
        {"ts_code":"600003.SH","name":"D","close":31,"pre_close":30,"amount":400},
    ]
    got = neutral_prefilter(rows, max_price=30, exclude_prefixes=["300","301"], exclude_st=True, min_amount=0, top_n=20)
    assert [x["ts_code"] for x in got] == ["600001.SH"]
