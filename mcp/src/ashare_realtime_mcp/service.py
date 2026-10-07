from __future__ import annotations

from datetime import datetime, timedelta

from .analytics import safe_float, pct_change, neutral_prefilter, percentile_ranks
from .cache import TTLCache
from .time_utils import now_shanghai, parse_market_time, freshness, market_phase
from .history_store import SnapshotStore
from .scanner import compare_stock_snapshots, discovery_rank
from .provider import ProviderPayload


def _records(data) -> list[dict]:
    if data is None:
        return []
    if hasattr(data, "where") and hasattr(data, "to_dict"):
        try:
            data = data.where(data.notna(), None)
        except Exception:
            pass
        return data.to_dict(orient="records")
    if isinstance(data, list):
        return [dict(x) for x in data]
    raise TypeError(f"Unsupported provider result type: {type(data)!r}")


def _max_as_of(rows: list[dict], keys=("trade_time", "time", "timestamp")) -> datetime | None:
    values = []
    for row in rows:
        for key in keys:
            dt = parse_market_time(row.get(key))
            if dt is not None:
                values.append(dt)
                break
    return max(values) if values else None


def _iso(dt: datetime | None):
    return dt.isoformat() if dt else None


class RealtimeService:
    FULL_MARKET_PATTERN = "3*.SZ,6*.SH,0*.SZ,4*.BJ,8*.BJ,9*.BJ"

    def __init__(self, provider, cache_seconds: int = 20,
                 snapshot_db_path: str = "./data/ashare_snapshots.sqlite3", retention_days: int = 10):
        self.provider = provider
        self.cache = TTLCache(cache_seconds)
        self.members_cache = TTLCache(21600)
        self.store = SnapshotStore(snapshot_db_path, retention_days)

    def _fetch(self, method: str, *args) -> tuple[list[dict], ProviderPayload]:
        result = getattr(self.provider, method)(*args)
        if not isinstance(result, ProviderPayload):
            result = ProviderPayload(result, getattr(self.provider, "name", "unknown"), method)
        return _records(result.data), result

    def _envelope(self, rows: list[dict], payload: ProviderPayload, *, warnings=None):
        retrieved = now_shanghai()
        as_of = payload.as_of or _max_as_of(rows)
        q = freshness(as_of, retrieved)
        all_warnings = [*payload.warnings, *(warnings or [])]
        return {
            "source": payload.source,
            "source_endpoint": payload.endpoint,
            "retrieved_at": retrieved.isoformat(),
            "as_of": _iso(as_of),
            "freshness_basis": payload.freshness_basis,
            **q,
            "warnings": all_warnings,
        }

    @staticmethod
    def _pct(r: dict):
        direct = safe_float(r.get("pct_change_raw"))
        return direct if direct is not None else pct_change(r.get("close"), r.get("pre_close"))

    def provider_status(self) -> dict:
        providers = getattr(self.provider, "providers", [self.provider])
        result = {
            "provider_order": [p.name for p in providers],
            "ok": False,
            "providers": {},
            "snapshot_store": self.store.stats(),
        }
        for p in providers:
            checks = {}
            specs = [
                ("stock_snapshot", lambda p=p: p.stock_snapshot("600000.SH")),
                ("sector_snapshot", lambda p=p: p.sector_snapshot(None)),
                ("minute_5m", lambda p=p: p.realtime_minutes("600000.SH", "5MIN")),
                ("sector_classes", lambda p=p: p.l1_sector_classes()),
            ]
            core_ok = True
            for name, fn in specs:
                try:
                    payload = fn()
                    rows = _records(payload.data)
                    env = self._envelope(rows, payload)
                    checks[name] = {
                        "ok": bool(rows), "rows": len(rows), "as_of": env["as_of"],
                        "freshness": env["freshness"], "source_endpoint": payload.endpoint,
                    }
                    if name in {"stock_snapshot", "sector_snapshot"} and not rows:
                        core_ok = False
                except Exception as exc:
                    checks[name] = {"ok": False, "error": type(exc).__name__, "message": str(exc)[:300]}
                    if name in {"stock_snapshot", "sector_snapshot"}:
                        core_ok = False
            result["providers"][p.name] = {"ok": core_ok, "checks": checks}
            result["ok"] = result["ok"] or core_ok
        return result

    def full_market(self) -> tuple[list[dict], ProviderPayload]:
        cached = self.cache.get("full_market_v34")
        if cached is not None:
            return cached
        rows, payload = self._fetch("stock_snapshot", self.FULL_MARKET_PATTERN)
        value = (rows, payload)
        self.cache.put("full_market_v34", value)
        return value

    def full_sectors(self) -> tuple[list[dict], ProviderPayload]:
        cached = self.cache.get("full_sectors_v34")
        if cached is not None:
            return cached
        rows, payload = self._fetch("sector_snapshot", None)
        value = (rows, payload)
        self.cache.put("full_sectors_v34", value)
        return value

    def _normalized_stocks(self, rows: list[dict]) -> list[dict]:
        out = []
        for r in rows:
            item = dict(r)
            item["last"] = safe_float(r.get("close"))
            item["pct_change"] = self._pct(r)
            out.append(item)
        return out

    def _normalized_sectors(self, rows: list[dict]) -> list[dict]:
        out = []
        for r in rows:
            item = dict(r)
            item["last"] = safe_float(r.get("close"))
            item["pct_change"] = self._pct(r)
            out.append(item)
        return out

    def market_snapshot(self) -> dict:
        rows, payload = self.full_market()
        changes = [self._pct(r) for r in rows]
        valid = [x for x in changes if x is not None]
        amounts = [safe_float(r.get("amount")) or 0.0 for r in rows]
        sorted_valid = sorted(valid)
        median = None
        if sorted_valid:
            n = len(sorted_valid)
            median = sorted_valid[n // 2] if n % 2 else (sorted_valid[n // 2 - 1] + sorted_valid[n // 2]) / 2
        return {
            **self._envelope(rows, payload),
            "universe_count": len(rows),
            "total_amount": round(sum(amounts), 2),
            "advancers": sum(1 for x in valid if x > 0),
            "decliners": sum(1 for x in valid if x < 0),
            "unchanged": sum(1 for x in valid if x == 0),
            "median_pct_change": round(median, 4) if median is not None else None,
            "limit_up": None,
            "limit_down": None,
            "limit_counts_note": "Not approximated from price change; use a dedicated limit-pool source if added later.",
        }

    def sector_snapshot(self, codes: list[str] | None = None, top_n: int = 50) -> dict:
        raw, payload = self.full_sectors()
        if codes:
            wanted = {str(c).strip() for c in codes if str(c).strip()}
            raw = [r for r in raw if str(r.get("ts_code")) in wanted or str(r.get("name")) in wanted]
        rows = self._normalized_sectors(raw)
        rows.sort(key=lambda x: x.get("pct_change") if x.get("pct_change") is not None else -9999, reverse=True)
        rows = rows[: max(1, min(int(top_n), 200))]
        return {**self._envelope(raw, payload), "sectors": rows}

    def stock_snapshot(self, codes: list[str]) -> dict:
        clean = [str(c).strip().upper() for c in codes if str(c).strip()]
        if not clean or len(clean) > 200:
            raise ValueError("codes must contain 1..200 stock codes")
        raw_all, payload = self.full_market()
        wanted = set(clean)
        raw = [r for r in raw_all if str(r.get("ts_code") or "").upper() in wanted]
        return {**self._envelope(raw_all, payload), "stocks": self._normalized_stocks(raw)}

    def realtime_universe(self, max_price: float = 30.0, exclude_prefixes: list[str] | None = None,
                          exclude_st: bool = True, min_amount: float = 0.0, top_n: int = 80) -> dict:
        raw, payload = self.full_market()
        rows = neutral_prefilter(
            raw, max_price=max_price, exclude_prefixes=exclude_prefixes or [], exclude_st=exclude_st,
            min_amount=min_amount, top_n=top_n,
        )
        return {
            **self._envelope(raw, payload),
            "prefilter_note": "Objective context reduction only; sorted by current turnover, not a recommendation score.",
            "filters": {"max_price": max_price, "exclude_prefixes": exclude_prefixes or [], "exclude_st": exclude_st, "min_amount": min_amount},
            "candidates": rows,
        }

    def realtime_minute_bars(self, codes: list[str], freq: str = "5MIN") -> dict:
        freq = freq.upper()
        if freq not in {"1MIN", "5MIN", "15MIN", "30MIN", "60MIN"}:
            raise ValueError("freq must be 1MIN/5MIN/15MIN/30MIN/60MIN")
        clean = [str(c).strip().upper() for c in codes if str(c).strip()]
        if not clean or len(clean) > 20:
            raise ValueError("codes must contain 1..20 stock codes in free-first mode")
        raw, payload = self._fetch("realtime_minutes", ",".join(clean), freq)
        return {**self._envelope(raw, payload), "freq": freq, "bars": raw}

    def intraday_minutes(self, code: str, freq: str = "1MIN", max_rows: int = 400) -> dict:
        freq = freq.upper()
        if freq not in {"1MIN", "5MIN", "15MIN", "30MIN", "60MIN"}:
            raise ValueError("freq must be 1MIN/5MIN/15MIN/30MIN/60MIN")
        code = str(code).strip().upper()
        if not code:
            raise ValueError("code is required")
        raw, payload = self._fetch("intraday_minutes", code, freq)
        raw.sort(key=lambda r: str(r.get("time") or ""))
        if max_rows > 0:
            raw = raw[-min(int(max_rows), 500):]
        closes = [safe_float(r.get("close")) for r in raw]
        highs = [safe_float(r.get("high")) for r in raw]
        lows = [safe_float(r.get("low")) for r in raw]
        amounts = [safe_float(r.get("amount")) or 0.0 for r in raw]
        vols = [safe_float(r.get("vol")) or 0.0 for r in raw]
        vwap = None
        vol_sum = sum(vols)
        if vol_sum > 0 and sum(amounts) > 0:
            # Some sources report amount in currency and volume in shares/hands; expose only when source semantics are consistent enough.
            vwap = round(sum(amounts) / vol_sum, 4)
        return {
            **self._envelope(raw, payload),
            "code": code,
            "freq": freq,
            "summary": {
                "last": next((v for v in reversed(closes) if v is not None), None),
                "intraday_high": max((v for v in highs if v is not None), default=None),
                "intraday_low": min((v for v in lows if v is not None), default=None),
                "vwap_raw_ratio": vwap,
                "vwap_note": "Raw amount/volume ratio; confirm provider volume unit before treating as exact price VWAP.",
                "row_count": len(raw),
            },
            "bars": raw,
        }

    def capture_snapshot(self) -> dict:
        now = now_shanghai()
        stock_raw, stock_payload = self.full_market()
        stock_rows = self._normalized_stocks(stock_raw)
        sector_raw, sector_payload = self.full_sectors()
        sector_rows = self._normalized_sectors(sector_raw)
        stock_env = self._envelope(stock_raw, stock_payload)
        sector_env = self._envelope(sector_raw, sector_payload)
        if market_phase(now) == "OPEN":
            allowed = {"LIVE", "NEAR_LIVE"}
            if stock_env.get("freshness") not in allowed or sector_env.get("freshness") not in allowed:
                return {
                    "skipped": True,
                    "reason": "SOURCE_NOT_FRESH_ENOUGH",
                    "observed_at": now.isoformat(),
                    "stock_source": stock_payload.source,
                    "sector_source": sector_payload.source,
                    "stock_as_of": stock_env.get("as_of"),
                    "sector_as_of": sector_env.get("as_of"),
                    "stock_freshness": stock_env.get("freshness"),
                    "sector_freshness": sector_env.get("freshness"),
                    "warnings": [*stock_env.get("warnings", []), *sector_env.get("warnings", [])],
                    "store": self.store.stats(),
                }
        capture_id = self.store.save_capture(
            now, stock_env.get("as_of"), sector_env.get("as_of"), stock_rows, sector_rows,
            stock_payload.source, sector_payload.source,
        )
        return {
            "skipped": False,
            "capture_id": capture_id,
            "observed_at": now.isoformat(),
            "stock_source": stock_payload.source,
            "sector_source": sector_payload.source,
            "stock_as_of": stock_env.get("as_of"),
            "sector_as_of": sector_env.get("as_of"),
            "stock_freshness": stock_env.get("freshness"),
            "sector_freshness": sector_env.get("freshness"),
            "stock_count": len(stock_rows),
            "sector_count": len(sector_rows),
            "warnings": [*stock_env.get("warnings", []), *sector_env.get("warnings", [])],
            "store": self.store.stats(),
        }

    def _find_prior(self, lookback_minutes: int, stock_source: str | None = None, sector_source: str | None = None):
        target = now_shanghai() - timedelta(minutes=lookback_minutes)
        return self.store.nearest_capture(
            target, max_gap_minutes=max(7, lookback_minutes // 2),
            stock_source=stock_source, sector_source=sector_source,
        )

    def _sector_acceleration(self, current_sector: list[dict], prior_capture_id: int) -> list[dict]:
        prior_map = {r["sector_code"]: r for r in self.store.sector_rows(prior_capture_id)}
        out = []
        for row in current_sector:
            p = prior_map.get(row.get("ts_code"))
            if not p:
                continue
            old_pct = safe_float(p.get("pct_change"))
            now_pct = safe_float(row.get("pct_change"))
            item = dict(row)
            item["prior_pct_change"] = old_pct
            item["accel_pct_points"] = None if old_pct is None or now_pct is None else round(now_pct - old_pct, 4)
            old_last = safe_float(p.get("last"))
            last = safe_float(row.get("last"))
            item["interval_return_pct"] = None if last is None or old_last in (None, 0) else round((last / old_last - 1) * 100, 4)
            out.append(item)
        return out

    def acceleration_snapshot(self, lookback_minutes: int = 15, top_n_sectors: int = 15, top_n_stocks: int = 60) -> dict:
        lookback_minutes = max(5, min(int(lookback_minutes), 120))
        stock_raw, stock_payload = self.full_market()
        stock_rows = self._normalized_stocks(stock_raw)
        sector_raw, sector_payload = self.full_sectors()
        sector_rows = self._normalized_sectors(sector_raw)
        prior = self._find_prior(lookback_minutes, stock_payload.source, sector_payload.source)
        if not prior:
            return {
                **self._envelope(stock_raw, stock_payload),
                "ok": False, "reason": "NO_PRIOR_SNAPSHOT", "lookback_minutes": lookback_minutes,
                "store": self.store.stats(),
                "instruction": "Keep the cloud snapshot worker enabled; it records one capture every 5 minutes during OPEN market phase.",
            }
        stock_cmp = compare_stock_snapshots(stock_rows, self.store.stock_rows(prior["id"]))
        sector_cmp = self._sector_acceleration(sector_rows, prior["id"])
        stock_cmp.sort(key=lambda x: x.get("accel_pct_points") if x.get("accel_pct_points") is not None else -9999, reverse=True)
        sector_cmp.sort(key=lambda x: x.get("accel_pct_points") if x.get("accel_pct_points") is not None else -9999, reverse=True)
        return {
            **self._envelope(stock_raw, stock_payload, warnings=sector_payload.warnings),
            "ok": True, "lookback_minutes": lookback_minutes, "prior_capture": prior,
            "sector_acceleration": sector_cmp[: max(1, min(int(top_n_sectors), 50))],
            "stock_acceleration": stock_cmp[: max(1, min(int(top_n_stocks), 200))],
        }

    def _members_for_l1(self, l1_code: str) -> list[dict]:
        key = f"members:{l1_code}"
        cached = self.members_cache.get(key)
        if cached is not None:
            return cached
        rows, _payload = self._fetch("sector_members", l1_code)
        self.members_cache.put(key, rows)
        return rows

    def scan_candidates(self, lookback_minutes: int = 15, max_price: float = 30.0,
                        exclude_prefixes: list[str] | None = None, exclude_st: bool = True,
                        min_amount: float = 50_000_000, top_sector_count: int = 6, top_n: int = 40) -> dict:
        lookback_minutes = max(5, min(int(lookback_minutes), 120))
        raw_stocks, stock_payload = self.full_market()
        universe = neutral_prefilter(raw_stocks, max_price=max_price, exclude_prefixes=exclude_prefixes or [],
                                     exclude_st=exclude_st, min_amount=min_amount, top_n=250)
        sector_raw, sector_payload = self.full_sectors()
        current_sector = self._normalized_sectors(sector_raw)
        prior = self._find_prior(lookback_minutes, stock_payload.source, sector_payload.source)
        if not prior:
            return {**self._envelope(raw_stocks, stock_payload), "ok": False, "reason": "NO_PRIOR_SNAPSHOT", "lookback_minutes": lookback_minutes, "store": self.store.stats()}

        sector_cmp = self._sector_acceleration(current_sector, prior["id"])
        if not sector_cmp:
            return {**self._envelope(raw_stocks, stock_payload), "ok": False, "reason": "NO_SECTOR_COMPARISON", "lookback_minutes": lookback_minutes}

        strength_ranks = percentile_ranks([safe_float(x.get("pct_change")) for x in sector_cmp])
        accel_ranks = percentile_ranks([safe_float(x.get("accel_pct_points")) for x in sector_cmp])
        for i, sec in enumerate(sector_cmp):
            vals = [v for v in (strength_ranks[i], accel_ranks[i]) if v is not None]
            sec["sector_discovery_score"] = round(sum(vals) / len(vals) * 100, 2) if vals else None
        sector_cmp.sort(key=lambda x: x.get("sector_discovery_score") if x.get("sector_discovery_score") is not None else -1, reverse=True)
        selected = sector_cmp[: max(1, min(int(top_sector_count), 12))]
        sector_metrics = {x["ts_code"]: x for x in sector_cmp if x.get("ts_code")}

        stock_to_sector = {}
        warnings = [*stock_payload.warnings, *sector_payload.warnings]
        for sec in selected:
            code = sec.get("ts_code")
            try:
                for member in self._members_for_l1(code):
                    stock_code = member.get("ts_code") or member.get("con_code")
                    if stock_code:
                        stock_to_sector[stock_code] = (code, sec.get("name") or member.get("l1_name") or "")
            except Exception as exc:
                warnings.append(f"{code}: {type(exc).__name__}: {str(exc)[:160]}")

        if not stock_to_sector:
            return {**self._envelope(raw_stocks, stock_payload), "ok": False, "reason": "SECTOR_MEMBERS_UNAVAILABLE", "selected_sectors": selected, "warnings": warnings}

        prior_stocks = {r["ts_code"]: r for r in self.store.stock_rows(prior["id"])}
        candidates = []
        for row in universe:
            if row.get("ts_code") not in stock_to_sector:
                continue
            p = prior_stocks.get(row.get("ts_code"))
            if not p:
                continue
            old_pct = safe_float(p.get("pct_change"))
            now_pct = safe_float(row.get("pct_change"))
            item = dict(row)
            item["accel_pct_points"] = None if old_pct is None or now_pct is None else round(now_pct - old_pct, 4)
            candidates.append(item)

        ranked = discovery_rank(candidates, sector_metrics, stock_to_sector, top_n=top_n)
        return {
            **self._envelope(raw_stocks, stock_payload),
            "ok": True,
            "lookback_minutes": lookback_minutes,
            "prior_capture": prior,
            "selected_sectors": selected,
            "candidate_count_before_rank": len(candidates),
            "candidates": ranked,
            "warnings": warnings,
            "score_note": "Discovery score is for candidate discovery only; it is not an entry score or probability.",
        }
