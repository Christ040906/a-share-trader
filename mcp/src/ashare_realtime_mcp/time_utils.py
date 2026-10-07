from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

SH_TZ = ZoneInfo("Asia/Shanghai")


def now_shanghai() -> datetime:
    return datetime.now(SH_TZ)


def parse_market_time(value: object) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none"}:
        return None
    # Common Tushare forms: 2026-04-15 09:31:00 / 09:31:00
    candidates = ["%Y-%m-%d %H:%M:%S", "%Y%m%d %H:%M:%S", "%H:%M:%S"]
    for fmt in candidates:
        try:
            dt = datetime.strptime(text, fmt)
            if fmt == "%H:%M:%S":
                today = now_shanghai().date()
                dt = datetime.combine(today, dt.time())
            return dt.replace(tzinfo=SH_TZ)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=SH_TZ)
        return dt.astimezone(SH_TZ)
    except ValueError:
        return None


def market_phase(now: datetime | None = None) -> str:
    now = now or now_shanghai()
    if now.weekday() >= 5:
        return "CLOSED"
    hm = now.hour * 60 + now.minute
    if 9 * 60 + 30 <= hm <= 11 * 60 + 30:
        return "OPEN"
    if 13 * 60 <= hm <= 15 * 60:
        return "OPEN"
    if 11 * 60 + 30 < hm < 13 * 60:
        return "PAUSED"
    return "CLOSED"


def freshness(as_of: datetime | None, now: datetime | None = None) -> dict:
    now = now or now_shanghai()
    phase = market_phase(now)
    if as_of is None:
        return {"freshness": "UNKNOWN", "age_minutes": None, "market_phase": phase}
    age = max(0.0, (now - as_of.astimezone(SH_TZ)).total_seconds() / 60.0)
    if phase == "PAUSED":
        label = "PAUSED"
    elif phase == "CLOSED":
        label = "CLOSED"
    elif age <= 1.0:
        label = "LIVE"
    elif age <= 5.0:
        label = "NEAR_LIVE"
    else:
        label = "STALE"
    return {"freshness": label, "age_minutes": round(age, 2), "market_phase": phase}
