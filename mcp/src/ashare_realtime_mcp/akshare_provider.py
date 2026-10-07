from __future__ import annotations

from datetime import datetime, timedelta
import time
from zoneinfo import ZoneInfo

from .provider import MarketDataProvider, ProviderPayload

SH_TZ = ZoneInfo("Asia/Shanghai")


def _num(v):
    try:
        if v is None or v == "-":
            return None
        x = float(v)
        return None if x != x else x
    except (TypeError, ValueError):
        return None


def _plain(code: str) -> str:
    c = str(code or "").strip().lower()
    if c.startswith(("sh", "sz", "bj")):
        c = c[2:]
    if "." in c:
        c = c.split(".", 1)[0]
    return c.zfill(6) if c.isdigit() else c


def _ts_code(code: str) -> str:
    c = _plain(code)
    if not c:
        return ""
    if c.startswith(("4", "8", "9")):
        return f"{c}.BJ"
    if c.startswith(("5", "6", "68")):
        return f"{c}.SH"
    return f"{c}.SZ"


def _sina_code(code: str) -> str:
    c = _plain(code)
    if c.startswith(("4", "8", "9")):
        return "bj" + c
    if c.startswith(("5", "6", "68")):
        return "sh" + c
    return "sz" + c


def _parse_time(text) -> datetime | None:
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    today = datetime.now(SH_TZ).date()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%H:%M:%S", "%H:%M"):
        try:
            dt = datetime.strptime(s, fmt)
            if fmt.startswith("%H"):
                dt = datetime.combine(today, dt.time())
            return dt.replace(tzinfo=SH_TZ)
        except ValueError:
            pass
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=SH_TZ)
        return dt.astimezone(SH_TZ)
    except ValueError:
        return None


class AkShareProvider(MarketDataProvider):
    """Free-first provider using AKShare.

    Rich snapshots use Eastmoney via AKShare. A lightweight benchmark-minute probe is
    used to verify market time because Eastmoney's full-market snapshot has no row
    timestamp. Sina is used only as a fallback for the stock snapshot path.
    """

    name = "akshare"

    def __init__(self, retries: int = 1, retry_delay_seconds: float = 0.4):
        try:
            import akshare as ak
        except ImportError as exc:
            raise RuntimeError("akshare package is not installed") from exc
        self.ak = ak
        self.retries = max(0, int(retries))
        self.retry_delay_seconds = max(0.0, float(retry_delay_seconds))
        self._sector_code_to_name: dict[str, str] = {}

    def _call(self, fn, *args, **kwargs):
        last = None
        for attempt in range(self.retries + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                last = exc
                if attempt < self.retries:
                    time.sleep(self.retry_delay_seconds * (attempt + 1))
        raise last

    def _market_clock(self) -> datetime | None:
        now = datetime.now(SH_TZ)
        start = now.strftime("%Y-%m-%d 09:30:00")
        end = now.strftime("%Y-%m-%d %H:%M:%S")
        try:
            df = self._call(
                self.ak.index_zh_a_hist_min_em,
                symbol="000001", period="1", start_date=start, end_date=end,
            )
            if df is None or len(df) == 0:
                return None
            col = "时间" if "时间" in df.columns else df.columns[0]
            return max((_parse_time(v) for v in df[col].tolist()), default=None)
        except Exception:
            return None

    def _normalize_em_spot(self, df):
        rows = []
        for r in df.to_dict(orient="records"):
            code = _ts_code(r.get("代码"))
            rows.append({
                "ts_code": code,
                "name": r.get("名称"),
                "pre_close": _num(r.get("昨收")),
                "open": _num(r.get("今开")),
                "high": _num(r.get("最高")),
                "low": _num(r.get("最低")),
                "close": _num(r.get("最新价")),
                "vol": _num(r.get("成交量")),
                "amount": _num(r.get("成交额")),
                "pct_change_raw": _num(r.get("涨跌幅")),
                "turnover_rate": _num(r.get("换手率")),
                "volume_ratio": _num(r.get("量比")),
                "speed": _num(r.get("涨速")),
                "pct_5m": _num(r.get("5分钟涨跌")),
                "trade_time": None,
            })
        return rows

    def _normalize_sina_spot(self, df):
        rows = []
        times = []
        for r in df.to_dict(orient="records"):
            code_raw = r.get("代码")
            code = _ts_code(code_raw)
            t = _parse_time(r.get("时间戳"))
            if t:
                times.append(t)
            rows.append({
                "ts_code": code,
                "name": r.get("名称"),
                "pre_close": _num(r.get("昨收")),
                "open": _num(r.get("今开")),
                "high": _num(r.get("最高")),
                "low": _num(r.get("最低")),
                "close": _num(r.get("最新价")),
                "vol": _num(r.get("成交量")),
                "amount": _num(r.get("成交额")),
                "pct_change_raw": _num(r.get("涨跌幅")),
                "turnover_rate": None,
                "volume_ratio": None,
                "speed": None,
                "pct_5m": None,
                "trade_time": t.isoformat() if t else None,
            })
        return rows, (max(times) if times else None)

    @staticmethod
    def _filter_codes(rows: list[dict], query: str) -> list[dict]:
        if not query or "*" in query:
            return rows
        wanted = {_ts_code(x.strip()) for x in query.split(",") if x.strip()}
        return [r for r in rows if r.get("ts_code") in wanted]

    def stock_snapshot(self, query: str) -> ProviderPayload:
        warnings = []
        try:
            df = self._call(self.ak.stock_zh_a_spot_em)
            rows = self._filter_codes(self._normalize_em_spot(df), query)
            clock = self._market_clock()
            if clock is None:
                warnings.append("AKShare Eastmoney snapshot has no row timestamp and market-clock probe was unavailable.")
            else:
                warnings.append("as_of is verified by Shanghai-index 1-minute clock; Eastmoney spot rows do not expose row timestamps.")
            return ProviderPayload(
                rows, self.name, "stock_zh_a_spot_em", as_of=clock,
                freshness_basis="benchmark_minute_probe" if clock else "retrieval_only", warnings=warnings,
            )
        except Exception as em_exc:
            warnings.append(f"Eastmoney spot failed: {type(em_exc).__name__}: {str(em_exc)[:180]}")
            df = self._call(self.ak.stock_zh_a_spot)
            rows, as_of = self._normalize_sina_spot(df)
            rows = self._filter_codes(rows, query)
            warnings.append("Fell back to AKShare Sina snapshot; repeated high-frequency use may trigger source throttling.")
            return ProviderPayload(
                rows, "akshare-sina", "stock_zh_a_spot", as_of=as_of,
                freshness_basis="row_timestamp", warnings=warnings,
            )

    def _sector_rows(self, df):
        rows = []
        self._sector_code_to_name = {}
        for r in df.to_dict(orient="records"):
            name = str(r.get("板块名称") or r.get("名称") or "").strip()
            code = str(r.get("板块代码") or r.get("代码") or "").strip()
            if not code:
                code = "AKIND:" + name
            if name:
                self._sector_code_to_name[code] = name
            rows.append({
                "ts_code": code,
                "name": name,
                "pre_close": None,
                "open": _num(r.get("今开")),
                "high": _num(r.get("最高")),
                "low": _num(r.get("最低")),
                "close": _num(r.get("最新价")),
                "amount": _num(r.get("成交额")),
                "pct_change_raw": _num(r.get("涨跌幅")),
                "turnover_rate": _num(r.get("换手率")),
                "up_count": _num(r.get("上涨家数")),
                "down_count": _num(r.get("下跌家数")),
                "leader": r.get("领涨股票"),
                "trade_time": None,
            })
        return rows

    def sector_snapshot(self, query: str | None = None) -> ProviderPayload:
        df = self._call(self.ak.stock_board_industry_name_em)
        rows = self._sector_rows(df)
        if query:
            wanted = {x.strip() for x in query.split(",") if x.strip()}
            rows = [r for r in rows if r.get("ts_code") in wanted or r.get("name") in wanted]
        clock = self._market_clock()
        return ProviderPayload(
            rows, self.name, "stock_board_industry_name_em", as_of=clock,
            freshness_basis="benchmark_minute_probe" if clock else "retrieval_only",
            warnings=["Industry-board rows have no per-row timestamp; as_of uses the Shanghai-index minute clock."] if clock else ["Industry-board rows have no per-row timestamp."],
        )

    def _minute_df(self, code: str, freq: str):
        plain = _plain(code)
        period = str(int(freq.upper().replace("MIN", "")))
        now = datetime.now(SH_TZ)
        start = now.strftime("%Y-%m-%d 09:30:00")
        end = now.strftime("%Y-%m-%d %H:%M:%S")
        try:
            return self._call(
                self.ak.stock_zh_a_hist_min_em,
                symbol=plain, period=period, start_date=start, end_date=end, adjust="",
            ), "stock_zh_a_hist_min_em"
        except Exception:
            return self._call(self.ak.stock_zh_a_minute, symbol=_sina_code(plain), period=period, adjust=""), "stock_zh_a_minute"

    def _normalize_minutes(self, df, code: str):
        out = []
        for r in df.to_dict(orient="records"):
            t = r.get("时间") if "时间" in r else r.get("day")
            dt = _parse_time(t)
            out.append({
                "ts_code": _ts_code(code),
                "time": dt.isoformat() if dt else (str(t) if t is not None else None),
                "open": _num(r.get("开盘") if "开盘" in r else r.get("open")),
                "close": _num(r.get("收盘") if "收盘" in r else r.get("close")),
                "high": _num(r.get("最高") if "最高" in r else r.get("high")),
                "low": _num(r.get("最低") if "最低" in r else r.get("low")),
                "vol": _num(r.get("成交量") if "成交量" in r else r.get("volume")),
                "amount": _num(r.get("成交额") if "成交额" in r else r.get("amount")),
            })
        return out

    def realtime_minutes(self, ts_codes: str, freq: str) -> ProviderPayload:
        codes = [x.strip() for x in ts_codes.split(",") if x.strip()]
        if len(codes) > 20:
            raise ValueError("AKShare minute-bar batch is capped at 20 codes per call to reduce source throttling risk")
        rows = []
        endpoints = set()
        warnings = []
        for code in codes:
            try:
                df, endpoint = self._minute_df(code, freq)
                endpoints.add(endpoint)
                rows.extend(self._normalize_minutes(df, code))
            except Exception as exc:
                warnings.append(f"{code}: {type(exc).__name__}: {str(exc)[:160]}")
        times = [_parse_time(r.get("time")) for r in rows]
        as_of = max((t for t in times if t), default=None)
        return ProviderPayload(
            rows, self.name, "+".join(sorted(endpoints)) or "minute_unavailable", as_of=as_of,
            freshness_basis="bar_timestamp", warnings=warnings,
        )

    def intraday_minutes(self, ts_code: str, freq: str) -> ProviderPayload:
        df, endpoint = self._minute_df(ts_code, freq)
        rows = self._normalize_minutes(df, ts_code)
        times = [_parse_time(r.get("time")) for r in rows]
        return ProviderPayload(
            rows, self.name, endpoint, as_of=max((t for t in times if t), default=None),
            freshness_basis="bar_timestamp",
        )

    def l1_sector_classes(self) -> ProviderPayload:
        payload = self.sector_snapshot(None)
        rows = [{"index_code": r.get("ts_code"), "industry_name": r.get("name"), "level": "L1-like"} for r in payload.data]
        return ProviderPayload(rows, payload.source, payload.endpoint, payload.as_of, payload.freshness_basis, payload.warnings)

    def sector_members(self, l1_code: str) -> ProviderPayload:
        if not self._sector_code_to_name:
            self.sector_snapshot(None)
        name = self._sector_code_to_name.get(l1_code)
        if not name and str(l1_code).startswith("AKIND:"):
            name = str(l1_code).split(":", 1)[1]
        if not name:
            name = str(l1_code)
        df = self._call(self.ak.stock_board_industry_cons_em, symbol=name)
        rows = []
        for r in df.to_dict(orient="records"):
            code = _ts_code(r.get("代码"))
            if code:
                rows.append({
                    "ts_code": code,
                    "name": r.get("名称"),
                    "l1_code": l1_code,
                    "l1_name": name,
                })
        return ProviderPayload(rows, self.name, "stock_board_industry_cons_em", freshness_basis="membership_snapshot")
