from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sqlite3


class SnapshotStore:
    def __init__(self, path: str, retention_days: int = 10):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.retention_days = max(1, int(retention_days))
        self._init()

    def _conn(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        sql = """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS captures (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          observed_at TEXT NOT NULL,
          stock_as_of TEXT,
          sector_as_of TEXT,
          stock_source TEXT,
          sector_source TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_captures_observed_at ON captures(observed_at);
        CREATE TABLE IF NOT EXISTS stock_snapshots (
          capture_id INTEGER NOT NULL,
          ts_code TEXT NOT NULL,
          name TEXT,
          last REAL,
          pre_close REAL,
          pct_change REAL,
          high REAL,
          low REAL,
          amount REAL,
          PRIMARY KEY(capture_id, ts_code)
        );
        CREATE INDEX IF NOT EXISTS ix_stock_code_capture ON stock_snapshots(ts_code, capture_id);
        CREATE TABLE IF NOT EXISTS sector_snapshots (
          capture_id INTEGER NOT NULL,
          sector_code TEXT NOT NULL,
          name TEXT,
          last REAL,
          pre_close REAL,
          pct_change REAL,
          amount REAL,
          PRIMARY KEY(capture_id, sector_code)
        );
        CREATE INDEX IF NOT EXISTS ix_sector_code_capture ON sector_snapshots(sector_code, capture_id);
        """
        with self._conn() as c:
            c.executescript(sql)
            cols = {r[1] for r in c.execute("PRAGMA table_info(captures)").fetchall()}
            if "stock_source" not in cols:
                c.execute("ALTER TABLE captures ADD COLUMN stock_source TEXT")
            if "sector_source" not in cols:
                c.execute("ALTER TABLE captures ADD COLUMN sector_source TEXT")

    def save_capture(self, observed_at: datetime, stock_as_of: str | None, sector_as_of: str | None,
                     stock_rows: list[dict], sector_rows: list[dict],
                     stock_source: str | None = None, sector_source: str | None = None) -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO captures(observed_at, stock_as_of, sector_as_of, stock_source, sector_source) VALUES(?,?,?,?,?)",
                (observed_at.isoformat(), stock_as_of, sector_as_of, stock_source, sector_source),
            )
            capture_id = int(cur.lastrowid)
            c.executemany(
                "INSERT OR REPLACE INTO stock_snapshots(capture_id,ts_code,name,last,pre_close,pct_change,high,low,amount) VALUES(?,?,?,?,?,?,?,?,?)",
                [(capture_id, r.get("ts_code"), r.get("name"), r.get("last"), r.get("pre_close"), r.get("pct_change"), r.get("high"), r.get("low"), r.get("amount"))
                 for r in stock_rows if r.get("ts_code")],
            )
            c.executemany(
                "INSERT OR REPLACE INTO sector_snapshots(capture_id,sector_code,name,last,pre_close,pct_change,amount) VALUES(?,?,?,?,?,?,?)",
                [(capture_id, r.get("ts_code"), r.get("name"), r.get("last") if r.get("last") is not None else r.get("close"), r.get("pre_close"), r.get("pct_change"), r.get("amount"))
                 for r in sector_rows if r.get("ts_code")],
            )
        self.cleanup(observed_at)
        return capture_id

    def cleanup(self, now: datetime):
        cutoff = (now - timedelta(days=self.retention_days)).isoformat()
        with self._conn() as c:
            old = [r[0] for r in c.execute("SELECT id FROM captures WHERE observed_at < ?", (cutoff,)).fetchall()]
            if not old:
                return
            q = ",".join("?" for _ in old)
            c.execute(f"DELETE FROM stock_snapshots WHERE capture_id IN ({q})", old)
            c.execute(f"DELETE FROM sector_snapshots WHERE capture_id IN ({q})", old)
            c.execute(f"DELETE FROM captures WHERE id IN ({q})", old)

    def nearest_capture(self, target: datetime, max_gap_minutes: int = 10,
                        stock_source: str | None = None, sector_source: str | None = None):
        sql = "SELECT * FROM captures WHERE observed_at <= ?"
        args: list[object] = [target.isoformat()]
        if stock_source:
            sql += " AND stock_source = ?"
            args.append(stock_source)
        if sector_source:
            sql += " AND sector_source = ?"
            args.append(sector_source)
        sql += " ORDER BY observed_at DESC LIMIT 1"
        with self._conn() as c:
            row = c.execute(sql, args).fetchone()
        if row is None:
            return None
        observed = datetime.fromisoformat(row["observed_at"])
        if (target - observed).total_seconds() / 60.0 > max_gap_minutes:
            return None
        return dict(row)

    def latest_capture(self):
        with self._conn() as c:
            row = c.execute("SELECT * FROM captures ORDER BY observed_at DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def stock_rows(self, capture_id: int) -> list[dict]:
        with self._conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM stock_snapshots WHERE capture_id=?", (capture_id,)).fetchall()]

    def sector_rows(self, capture_id: int) -> list[dict]:
        with self._conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM sector_snapshots WHERE capture_id=?", (capture_id,)).fetchall()]

    def stats(self) -> dict:
        with self._conn() as c:
            captures = c.execute("SELECT COUNT(*) FROM captures").fetchone()[0]
            latest = c.execute("SELECT observed_at,stock_source,sector_source FROM captures ORDER BY observed_at DESC LIMIT 1").fetchone()
            stocks = c.execute("SELECT COUNT(*) FROM stock_snapshots").fetchone()[0]
            sectors = c.execute("SELECT COUNT(*) FROM sector_snapshots").fetchone()[0]
        return {
            "captures": captures,
            "stock_rows": stocks,
            "sector_rows": sectors,
            "latest_capture": latest[0] if latest else None,
            "latest_stock_source": latest[1] if latest else None,
            "latest_sector_source": latest[2] if latest else None,
        }
