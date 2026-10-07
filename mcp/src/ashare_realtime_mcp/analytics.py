from __future__ import annotations

from typing import Iterable


def safe_float(value):
    try:
        if value is None:
            return None
        v = float(value)
        if v != v:  # NaN
            return None
        return v
    except (TypeError, ValueError):
        return None


def pct_change(last, pre_close):
    last = safe_float(last)
    pre_close = safe_float(pre_close)
    if last is None or pre_close in (None, 0):
        return None
    return round((last / pre_close - 1.0) * 100.0, 4)


def intraday_position(last, low, high):
    last, low, high = safe_float(last), safe_float(low), safe_float(high)
    if last is None or low is None or high is None or high <= low:
        return None
    return round((last - low) / (high - low), 4)


def percentile_ranks(values: list[float | None]) -> list[float | None]:
    valid = sorted(v for v in values if v is not None)
    n = len(valid)
    if not n:
        return [None] * len(values)
    def rank(v):
        if v is None:
            return None
        # mid-ish empirical rank; ties need not be exact for neutral prefiltering
        le = sum(x <= v for x in valid)
        return round(le / n, 4)
    return [rank(v) for v in values]


def neutral_prefilter(rows: list[dict], *, max_price: float | None, exclude_prefixes: Iterable[str], exclude_st: bool,
                      min_amount: float, top_n: int) -> list[dict]:
    prefixes = tuple(exclude_prefixes)
    kept = []
    for row in rows:
        code = str(row.get("ts_code") or "")
        name = str(row.get("name") or "")
        last = safe_float(row.get("close"))
        amount = safe_float(row.get("amount")) or 0.0
        if not code or last is None or last <= 0:
            continue
        plain = code.split('.')[0]
        if prefixes and plain.startswith(prefixes):
            continue
        if exclude_st and ("ST" in name.upper() or "退" in name):
            continue
        if max_price is not None and last > max_price:
            continue
        if amount < min_amount:
            continue
        item = dict(row)
        item["last"] = last
        item["pct_change"] = pct_change(last, row.get("pre_close"))
        item["intraday_position"] = intraday_position(last, row.get("low"), row.get("high"))
        kept.append(item)

    # Do not turn this into a recommendation score. Use liquidity to cap context,
    # while exposing strength/position for the Skill to reason about.
    kept.sort(key=lambda x: safe_float(x.get("amount")) or 0.0, reverse=True)
    return kept[: max(1, min(int(top_n), 200))]
