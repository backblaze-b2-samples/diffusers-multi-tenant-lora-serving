"""SQLite job queue, run index and worker registry (stdlib `sqlite3`, WAL).

One dispatcher process owns this file. Every mutation runs under one lock and
one transaction, so a claim can never hand the same job to two workers.
Rows are plain dicts; the service layer turns them into API models.
"""

import json
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any

from app.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, report_key TEXT
);
CREATE TABLE IF NOT EXISTS jobs (
  job_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, tenant_id TEXT NOT NULL,
  adapter TEXT, version TEXT, adapter_sha256 TEXT, adapter_size INTEGER,
  adapter_tenant TEXT, weight_key TEXT, base_model TEXT NOT NULL, scale REAL,
  state TEXT NOT NULL, attempt INTEGER NOT NULL DEFAULT 0, worker_id TEXT,
  seed INTEGER NOT NULL, steps INTEGER NOT NULL, width INTEGER NOT NULL,
  height INTEGER NOT NULL, prompt TEXT NOT NULL, negative_prompt TEXT,
  output_key TEXT NOT NULL, lease_expires_at REAL, step INTEGER,
  cache TEXT, bytes_fetched INTEGER, sha256_verified INTEGER,
  fetch_ms INTEGER, load_ms INTEGER, generate_ms INTEGER, unload_ms INTEGER,
  total_ms INTEGER, output_sha256 TEXT, adapters_after_unload TEXT,
  error_code TEXT, error_message TEXT, device TEXT,
  created_at TEXT NOT NULL, started_at REAL, finished_at TEXT,
  phase TEXT, heartbeat_at REAL
);
CREATE INDEX IF NOT EXISTS jobs_state ON jobs(state, created_at);
CREATE INDEX IF NOT EXISTS jobs_run ON jobs(run_id);
CREATE TABLE IF NOT EXISTS workers (
  worker_id TEXT PRIMARY KEY, device TEXT, dtype TEXT, base_model TEXT,
  last_seen REAL NOT NULL, jobs_done INTEGER NOT NULL DEFAULT 0,
  cache_entries INTEGER NOT NULL DEFAULT 0, cache_bytes INTEGER NOT NULL DEFAULT 0
);
"""

# Columns added after the first release: ALTER an existing jobs.db in place.
_ADDED_JOB_COLUMNS = {"phase": "TEXT", "heartbeat_at": "REAL"}

_lock = RLock()
_conn: sqlite3.Connection | None = None
_conn_path: str | None = None


def db_path() -> Path:
    p = Path(settings.jobs_db_path)
    if not p.is_absolute():
        # repo/ -> app/ -> services/api/
        p = Path(__file__).resolve().parents[2] / p
    return p


def _db() -> sqlite3.Connection:
    """The shared connection, reopened when the configured path changes (tests)."""
    global _conn, _conn_path
    path = str(db_path())
    if _conn is None or _conn_path != path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA)
        have = {r["name"] for r in conn.execute("PRAGMA table_info(jobs)")}
        for col, kind in _ADDED_JOB_COLUMNS.items():
            if col not in have:
                conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {kind}")
        _conn, _conn_path = conn, path
    return _conn


def _row(r: sqlite3.Row | None) -> dict[str, Any] | None:
    if r is None:
        return None
    d = dict(r)
    if d.get("adapters_after_unload") is not None:
        d["adapters_after_unload"] = json.loads(d["adapters_after_unload"])
    if d.get("sha256_verified") is not None:
        d["sha256_verified"] = bool(d["sha256_verified"])
    return d


def ensure_run(run_id: str, created_at: str) -> None:
    with _lock:
        _db().execute(
            "INSERT OR IGNORE INTO runs(run_id, created_at) VALUES (?, ?)", (run_id, created_at)
        )


def insert_jobs(rows: list[dict[str, Any]]) -> None:
    """Insert several queued jobs in one transaction (all or nothing)."""
    with _lock:
        db = _db()
        db.execute("BEGIN IMMEDIATE")
        try:
            for row in rows:
                cols = ", ".join(row)
                marks = ", ".join("?" for _ in row)
                db.execute(f"INSERT INTO jobs({cols}) VALUES ({marks})", tuple(row.values()))
            db.execute("COMMIT")
        except Exception:
            db.execute("ROLLBACK")
            raise


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        return _row(_db().execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone())


def list_jobs(
    tenant_id: str | None = None, state: str | None = None, run_id: str | None = None,
    limit: int = 500, oldest_first: bool = False,
) -> list[dict[str, Any]]:
    where, args = [], []
    for col, val in (("tenant_id", tenant_id), ("state", state), ("run_id", run_id)):
        if val is not None:
            where.append(f"{col} = ?")
            args.append(val)
    sql = "SELECT * FROM jobs"
    if where:
        sql += " WHERE " + " AND ".join(where)
    order = "ASC" if oldest_first else "DESC"
    sql += f" ORDER BY created_at {order}, rowid {order} LIMIT ?"
    with _lock:
        rows = _db().execute(sql, (*args, limit)).fetchall()
    return [_row(r) for r in rows]  # type: ignore[misc]


def expire_leases(now: float, max_attempts: int) -> list[dict[str, Any]]:
    """Re-queue running jobs whose lease ran out; fail those out of attempts.

    Returns the jobs that became terminal (`failed: lease_exhausted`).
    """
    with _lock:
        db = _db()
        db.execute("BEGIN IMMEDIATE")
        try:
            expired = db.execute(
                "SELECT job_id, attempt FROM jobs WHERE state = 'running' AND lease_expires_at < ?",
                (now,),
            ).fetchall()
            failed: list[str] = []
            for r in expired:
                if r["attempt"] >= max_attempts:
                    db.execute(
                        "UPDATE jobs SET state='failed', error_code='lease_exhausted', "
                        "error_message='worker stopped heartbeating on every attempt', "
                        "finished_at=strftime('%Y-%m-%dT%H:%M:%SZ','now'), lease_expires_at=NULL "
                        "WHERE job_id = ?",
                        (r["job_id"],),
                    )
                    failed.append(r["job_id"])
                else:
                    db.execute(
                        "UPDATE jobs SET state='queued', lease_expires_at=NULL, step=NULL, phase=NULL "
                        "WHERE job_id = ?",
                        (r["job_id"],),
                    )
            db.execute("COMMIT")
        except Exception:
            db.execute("ROLLBACK")
            raise
    return [j for j in (get_job(jid) for jid in failed) if j]


def claim_next(worker_id: str, now: float, lease_seconds: int) -> dict[str, Any] | None:
    """Atomically move the oldest queued job to running for `worker_id`."""
    with _lock:
        db = _db()
        db.execute("BEGIN IMMEDIATE")
        try:
            r = db.execute(
                "SELECT job_id FROM jobs WHERE state = 'queued' ORDER BY created_at, rowid LIMIT 1"
            ).fetchone()
            if r is None:
                db.execute("COMMIT")
                return None
            db.execute(
                "UPDATE jobs SET state='running', worker_id=?, attempt=attempt+1, "
                "lease_expires_at=?, started_at=?, heartbeat_at=?, step=NULL, phase=NULL "
                "WHERE job_id=?",
                (worker_id, now + lease_seconds, now, now, r["job_id"]),
            )
            db.execute("COMMIT")
        except Exception:
            db.execute("ROLLBACK")
            raise
        return get_job(r["job_id"])


def update_job_if_current(
    job_id: str, worker_id: str, attempt: int, fields: dict[str, Any]
) -> bool:
    """Apply `fields` only while (worker_id, attempt) still owns the running job."""
    if "adapters_after_unload" in fields:
        fields = {**fields, "adapters_after_unload": json.dumps(fields["adapters_after_unload"])}
    sets = ", ".join(f"{k} = ?" for k in fields)
    with _lock:
        cur = _db().execute(
            f"UPDATE jobs SET {sets} WHERE job_id = ? AND worker_id = ? AND attempt = ? "
            "AND state = 'running'",
            (*fields.values(), job_id, worker_id, attempt),
        )
        return cur.rowcount == 1


def get_run(run_id: str) -> dict[str, Any] | None:
    with _lock:
        r = _db().execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    return dict(r) if r else None


def list_runs(limit: int = 200) -> list[dict[str, Any]]:
    with _lock:
        rows = _db().execute(
            "SELECT r.run_id, r.created_at, r.report_key, COUNT(j.job_id) AS job_count, "
            "SUM(CASE WHEN j.state IN ('queued','running') THEN 1 ELSE 0 END) AS active "
            "FROM runs r LEFT JOIN jobs j ON j.run_id = r.run_id "
            "GROUP BY r.run_id ORDER BY r.created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def set_report_key(run_id: str, key: str) -> None:
    with _lock:
        _db().execute("UPDATE runs SET report_key = ? WHERE run_id = ?", (key, run_id))


def upsert_worker(hello: dict[str, Any], now: float) -> None:
    with _lock:
        _db().execute(
            "INSERT INTO workers(worker_id, device, dtype, base_model, last_seen, cache_entries,"
            " cache_bytes) VALUES (:worker_id, :device, :dtype, :base_model, :now,"
            " :cache_entries, :cache_bytes) ON CONFLICT(worker_id) DO UPDATE SET"
            " device=excluded.device, dtype=excluded.dtype, base_model=excluded.base_model,"
            " last_seen=excluded.last_seen, cache_entries=excluded.cache_entries,"
            " cache_bytes=excluded.cache_bytes",
            {**hello, "now": now},
        )


def touch_worker(worker_id: str, now: float, *, job_done: bool = False) -> None:
    with _lock:
        _db().execute(
            "UPDATE workers SET last_seen = ?, jobs_done = jobs_done + ? WHERE worker_id = ?",
            (now, 1 if job_done else 0, worker_id),
        )


def get_worker(worker_id: str) -> dict[str, Any] | None:
    with _lock:
        r = _db().execute("SELECT * FROM workers WHERE worker_id = ?", (worker_id,)).fetchone()
    return dict(r) if r else None


def list_workers() -> list[dict[str, Any]]:
    with _lock:
        rows = _db().execute(
            "SELECT w.*, (SELECT job_id FROM jobs j WHERE j.worker_id = w.worker_id AND"
            " j.state = 'running' LIMIT 1) AS current_job_id FROM workers w"
            " ORDER BY w.worker_id"
        ).fetchall()
    return [dict(r) for r in rows]


def reset_for_tests() -> None:
    """Close the connection so the next call opens the (monkeypatched) path."""
    global _conn, _conn_path
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn, _conn_path = None, None
