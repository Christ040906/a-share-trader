from __future__ import annotations

from .config import Settings
from .service import RealtimeService
from .provider_router import ProviderRouter
from .worker import start_worker_thread

try:
    from mcp.server import MCPServer
except ImportError:
    from mcp.server.mcpserver import MCPServer

settings = Settings.from_env()
mcp = MCPServer(
    "a-share-realtime",
    instructions=(
        "Read-only China A-share market-data tools. Free-first mode uses AKShare and can fall back to configured paid providers. "
        "For intraday decisions, inspect as_of, freshness, freshness_basis and warnings. retrieved_at is never market time. "
        "Do not present STALE/UNKNOWN data as live. Discovery scores only rank candidates and are not buy probabilities."
    ),
)
_service = None
_worker_started = False


def build_provider_router() -> ProviderRouter:
    providers = []
    errors = []
    for name in settings.provider_order:
        try:
            if name == "akshare":
                from .akshare_provider import AkShareProvider
                providers.append(AkShareProvider(retries=settings.akshare_retries))
            elif name == "tushare":
                if not settings.tushare_token:
                    continue
                from .tushare_provider import TushareProvider
                providers.append(TushareProvider(settings.tushare_token))
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
    if not providers:
        raise RuntimeError("No provider initialized. " + " | ".join(errors))
    return ProviderRouter(providers)


def service() -> RealtimeService:
    global _service
    if _service is None:
        _service = RealtimeService(
            build_provider_router(), settings.cache_seconds,
            settings.snapshot_db_path, settings.snapshot_retention_days,
        )
    return _service


@mcp.tool()
def provider_status() -> dict:
    """Check configured data providers, core endpoints, data freshness, and snapshot-store status."""
    return service().provider_status()


@mcp.tool()
def get_market_snapshot() -> dict:
    """Get current A-share market breadth. Always inspect freshness before intraday use."""
    return service().market_snapshot()


@mcp.tool()
def get_sector_snapshot(codes: list[str] | None = None, top_n: int = 50) -> dict:
    """Get current industry-board snapshots sorted by percentage change."""
    return service().sector_snapshot(codes, top_n)


@mcp.tool()
def get_stock_snapshot(codes: list[str]) -> dict:
    """Get current quote snapshots for 1 to 200 A-share stock codes."""
    return service().stock_snapshot(codes)


@mcp.tool()
def get_realtime_universe(max_price: float = 30.0, exclude_prefixes: list[str] | None = None,
                          exclude_st: bool = True, min_amount: float = 0.0, top_n: int = 80) -> dict:
    """Reduce the live universe with objective constraints and liquidity. This is not a buy ranking."""
    return service().realtime_universe(max_price, exclude_prefixes, exclude_st, min_amount, top_n)


@mcp.tool()
def get_realtime_minute_bars(codes: list[str], freq: str = "5MIN") -> dict:
    """Get current minute bars for up to 20 stocks in free-first mode."""
    return service().realtime_minute_bars(codes, freq)


@mcp.tool()
def get_intraday_minutes(code: str, freq: str = "1MIN", max_rows: int = 400) -> dict:
    """Get one stock's intraday minute series from open to now with freshness metadata."""
    return service().intraday_minutes(code, freq, max_rows)


@mcp.tool()
def capture_snapshot() -> dict:
    """Persist the current full-market and industry snapshots for later acceleration comparison."""
    return service().capture_snapshot()


@mcp.tool()
def get_acceleration_snapshot(lookback_minutes: int = 15, top_n_sectors: int = 15, top_n_stocks: int = 60) -> dict:
    """Compare current data with a stored snapshot to identify sectors and stocks strengthening now."""
    return service().acceleration_snapshot(lookback_minutes, top_n_sectors, top_n_stocks)


@mcp.tool()
def scan_realtime_candidates(lookback_minutes: int = 15, max_price: float = 30.0,
                             exclude_prefixes: list[str] | None = None, exclude_st: bool = True,
                             min_amount: float = 50_000_000.0, top_sector_count: int = 6, top_n: int = 40) -> dict:
    """Discover a compact live candidate set from strong/accelerating industries and stock relative strength. Not an entry score."""
    return service().scan_candidates(lookback_minutes, max_price, exclude_prefixes, exclude_st, min_amount, top_sector_count, top_n)


try:
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_request: Request):
        return JSONResponse({
            "status": "ok",
            "service": "a-share-realtime",
            "version": "0.4.0",
            "snapshot_worker_enabled": settings.snapshot_worker_enabled,
        })
except Exception:
    # MCP remains usable even if custom routes are unavailable in an older SDK build.
    pass


def main() -> None:
    global _worker_started
    svc = service()
    if settings.snapshot_worker_enabled and not _worker_started:
        start_worker_thread(svc, settings.snapshot_interval_seconds)
        _worker_started = True
    mcp.run(
        transport="streamable-http", host=settings.host, port=settings.port,
        streamable_http_path="/mcp", stateless_http=True, json_response=True,
    )


if __name__ == "__main__":
    main()
