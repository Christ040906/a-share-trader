from __future__ import annotations

import threading
import time

from .time_utils import market_phase, now_shanghai


def worker_loop(service, interval_seconds: int = 300, stop_event: threading.Event | None = None):
    interval = max(60, int(interval_seconds))
    stop_event = stop_event or threading.Event()
    print(f"snapshot worker started; interval={interval}s", flush=True)
    while not stop_event.is_set():
        if market_phase(now_shanghai()) == "OPEN":
            try:
                result = service.capture_snapshot()
                if result.get("skipped"):
                    print(
                        f"capture skipped at {result['observed_at']}: {result.get('reason')} "
                        f"stock={result.get('stock_freshness')} sector={result.get('sector_freshness')}",
                        flush=True,
                    )
                else:
                    print(
                        f"captured {result['capture_id']} at {result['observed_at']} "
                        f"stocks={result['stock_count']} sectors={result['sector_count']}",
                        flush=True,
                    )
            except Exception as exc:
                print(f"capture failed: {type(exc).__name__}: {exc}", flush=True)
        stop_event.wait(interval)


def start_worker_thread(service, interval_seconds: int = 300) -> threading.Thread:
    thread = threading.Thread(
        target=worker_loop,
        args=(service, interval_seconds),
        name="ashare-snapshot-worker",
        daemon=True,
    )
    thread.start()
    return thread


def main():
    from .server import service, settings
    worker_loop(service(), settings.snapshot_interval_seconds)


if __name__ == "__main__":
    main()
