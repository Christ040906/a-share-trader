from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    provider_order: tuple[str, ...]
    tushare_token: str
    host: str = "0.0.0.0"
    port: int = 8000
    cache_seconds: int = 20
    snapshot_db_path: str = "./data/ashare_snapshots.sqlite3"
    snapshot_retention_days: int = 3
    snapshot_worker_enabled: bool = True
    snapshot_interval_seconds: int = 300
    akshare_retries: int = 1

    @classmethod
    def from_env(cls) -> "Settings":
        order_raw = os.getenv("MARKET_DATA_PROVIDER_ORDER", "akshare,tushare")
        order = tuple(x.strip().lower() for x in order_raw.split(",") if x.strip())
        if not order:
            order = ("akshare",)
        port_raw = os.getenv("MCP_PORT") or os.getenv("PORT") or "8000"
        worker_raw = os.getenv("ENABLE_SNAPSHOT_WORKER", "true").strip().lower()
        return cls(
            provider_order=order,
            tushare_token=os.getenv("TUSHARE_TOKEN", "").strip(),
            host=os.getenv("MCP_HOST", "0.0.0.0"),
            port=int(port_raw),
            cache_seconds=max(0, int(os.getenv("MCP_CACHE_SECONDS", "20"))),
            snapshot_db_path=os.getenv("SNAPSHOT_DB_PATH", "/data/ashare_snapshots.sqlite3" if os.path.exists("/data") else "./data/ashare_snapshots.sqlite3"),
            snapshot_retention_days=max(1, int(os.getenv("SNAPSHOT_RETENTION_DAYS", "3"))),
            snapshot_worker_enabled=worker_raw in {"1", "true", "yes", "on"},
            snapshot_interval_seconds=max(60, int(os.getenv("SNAPSHOT_INTERVAL_SECONDS", "300"))),
            akshare_retries=max(0, int(os.getenv("AKSHARE_RETRIES", "1"))),
        )
