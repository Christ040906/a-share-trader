from ashare_realtime_mcp.scanner import discovery_rank

def test_discovery_rank_prefers_stronger_context():
    rows = [
        {"ts_code":"A.SH","pct_change":4,"accel_pct_points":1.2,"amount":1000},
        {"ts_code":"B.SH","pct_change":2,"accel_pct_points":0.2,"amount":900},
    ]
    sectors = {
        "S1.SI":{"pct_change":3,"accel_pct_points":1},
        "S2.SI":{"pct_change":1,"accel_pct_points":0},
    }
    mapping = {"A.SH":("S1.SI","S1"),"B.SH":("S2.SI","S2")}
    out = discovery_rank(rows,sectors,mapping,10)
    assert out[0]["ts_code"] == "A.SH"
    assert out[0]["discovery_score"] > out[1]["discovery_score"]
