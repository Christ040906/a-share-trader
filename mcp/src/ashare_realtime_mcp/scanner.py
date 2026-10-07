from __future__ import annotations
from .analytics import safe_float, percentile_ranks


def compare_stock_snapshots(current: list[dict], prior: list[dict]) -> list[dict]:
    prev = {str(r.get("ts_code")): r for r in prior if r.get("ts_code")}
    out = []
    for row in current:
        code = str(row.get("ts_code") or "")
        p = prev.get(code)
        if not p:
            continue
        now_pct = safe_float(row.get("pct_change"))
        old_pct = safe_float(p.get("pct_change"))
        item = dict(row)
        item["prior_pct_change"] = old_pct
        item["accel_pct_points"] = None if now_pct is None or old_pct is None else round(now_pct - old_pct, 4)
        out.append(item)
    return out


def discovery_rank(rows: list[dict], sector_metrics: dict[str, dict], stock_to_sector: dict[str, tuple[str, str]], top_n: int = 40) -> list[dict]:
    prepared = []
    for r in rows:
        code = str(r.get("ts_code") or "")
        smeta = stock_to_sector.get(code)
        if not smeta:
            continue
        sector_code, sector_name = smeta
        sec = sector_metrics.get(sector_code)
        if not sec:
            continue
        item = dict(r)
        item["sector_code"] = sector_code
        item["sector_name"] = sector_name
        stock_pct = safe_float(r.get("pct_change"))
        sector_pct = safe_float(sec.get("pct_change"))
        item["stock_vs_sector_pp"] = None if stock_pct is None or sector_pct is None else round(stock_pct - sector_pct, 4)
        item["sector_pct_change"] = sector_pct
        item["sector_accel_pct_points"] = safe_float(sec.get("accel_pct_points"))
        prepared.append(item)

    if not prepared:
        return []

    fields = ["sector_pct_change", "sector_accel_pct_points", "stock_vs_sector_pp", "accel_pct_points", "amount"]
    weights = [0.30, 0.25, 0.20, 0.15, 0.10]
    ranks = {f: percentile_ranks([safe_float(x.get(f)) for x in prepared]) for f in fields}

    for i, item in enumerate(prepared):
        score = 0.0
        used = 0.0
        components = []
        for f, w in zip(fields, weights):
            r = ranks[f][i]
            if r is None:
                continue
            score += r * w
            used += w
            components.append({"factor": f, "percentile": round(r, 4), "weight": w})
        item["discovery_score"] = round(score / used * 100.0, 2) if used else None
        item["discovery_components"] = components

    prepared.sort(key=lambda x: x.get("discovery_score") if x.get("discovery_score") is not None else -1, reverse=True)
    return prepared[: max(1, min(int(top_n), 100))]
