"""SQLite append-only results store and immutable prediction store."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .logging_util import utcnow
from .rules import ValidationError, missing_periods, normalize_colour, validate_result

SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS results (
    period_id TEXT PRIMARY KEY,
    result_number INTEGER NOT NULL CHECK (result_number BETWEEN 0 AND 9),
    result_colour TEXT NOT NULL,
    result_size TEXT NOT NULL CHECK (result_size IN ('Small','Big')),
    result_timestamp TEXT NOT NULL,
    source_url TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    stored_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_results_number ON results(result_number);

CREATE TABLE IF NOT EXISTS predictions (
    prediction_id TEXT PRIMARY KEY,
    period_id TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    data_cutoff_period TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    algorithm_version TEXT NOT NULL,
    number_probs TEXT NOT NULL,
    colour_probs TEXT NOT NULL,
    big_prob REAL NOT NULL,
    small_prob REAL NOT NULL,
    selected_number INTEGER NOT NULL,
    selected_colour TEXT NOT NULL,
    selected_size TEXT NOT NULL,
    sample_count INTEGER NOT NULL,
    model_config TEXT NOT NULL,
    prediction_status TEXT NOT NULL CHECK (prediction_status IN ('draft','published','evaluated')),
    is_late INTEGER NOT NULL DEFAULT 0,
    created_after_start_ms INTEGER,
    actual_number INTEGER,
    evaluated_at TEXT
);

-- Published predictions may only transition to 'evaluated' with their actual
-- outcome metadata. All model content is immutable.
CREATE TRIGGER IF NOT EXISTS predictions_immutable
BEFORE UPDATE ON predictions
WHEN OLD.prediction_status IN ('published','evaluated') AND (
    NEW.prediction_id IS NOT OLD.prediction_id OR
    NEW.period_id IS NOT OLD.period_id OR
    NEW.created_at IS NOT OLD.created_at OR
    NEW.data_cutoff_period IS NOT OLD.data_cutoff_period OR
    NEW.dataset_version IS NOT OLD.dataset_version OR
    NEW.algorithm_version IS NOT OLD.algorithm_version OR
    NEW.number_probs IS NOT OLD.number_probs OR
    NEW.colour_probs IS NOT OLD.colour_probs OR
    NEW.big_prob IS NOT OLD.big_prob OR
    NEW.small_prob IS NOT OLD.small_prob OR
    NEW.selected_number IS NOT OLD.selected_number OR
    NEW.selected_colour IS NOT OLD.selected_colour OR
    NEW.selected_size IS NOT OLD.selected_size OR
    NEW.sample_count IS NOT OLD.sample_count OR
    NEW.model_config IS NOT OLD.model_config OR
    NEW.is_late IS NOT OLD.is_late OR
    NEW.created_after_start_ms IS NOT OLD.created_after_start_ms OR
    (OLD.prediction_status = 'evaluated' AND NEW.prediction_status IS NOT OLD.prediction_status)
)
BEGIN
    SELECT RAISE(ABORT, 'prediction model content is immutable after publication');
END;

CREATE TABLE IF NOT EXISTS evaluations (
    prediction_id TEXT PRIMARY KEY,
    period_id TEXT NOT NULL UNIQUE,
    exact_number_hit INTEGER NOT NULL,
    colour_hit INTEGER NOT NULL,
    size_hit INTEGER NOT NULL,
    log_loss REAL NOT NULL,
    brier_score REAL NOT NULL,
    baseline_log_loss REAL NOT NULL,
    baseline_brier REAL NOT NULL,
    calibration TEXT NOT NULL,
    evaluated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feed_state (
    feed_key TEXT PRIMARY KEY,
    etag TEXT,
    last_modified TEXT,
    last_request_at TEXT,
    last_request_epoch REAL,
    last_success_at TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    last_status TEXT,
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS collector_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    level TEXT NOT NULL,
    event TEXT NOT NULL,
    details TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class Store:
    """Thread-safe SQLite store. All writes are append-only where required."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self.migrate()

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self.db_path), timeout=15, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=15000")
            self._local.conn = conn
        return conn

    @contextmanager
    def transaction(self):
        conn = self._conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def migrate(self) -> None:
        """Non-destructive, idempotent migration. Adds columns/indexes if absent."""
        conn = self._conn()
        # ensure trigger definition is refreshed on every startup
        conn.execute("DROP TRIGGER IF EXISTS predictions_immutable")
        conn.executescript(SCHEMA)
        self._ensure_column(conn, "predictions", "is_late", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column(conn, "predictions", "created_after_start_ms", "INTEGER")
        self._ensure_column(conn, "feed_state", "last_request_epoch", "REAL")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_results_timestamp ON results(result_timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_predictions_status ON predictions(prediction_status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_evaluations_period ON evaluations(period_id)")
        conn.execute(
            "INSERT INTO schema_meta(key,value) VALUES('schema_version',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(SCHEMA_VERSION),)
        )
        conn.commit()

    @staticmethod
    def _ensure_column(conn, table: str, column: str, definition: str) -> None:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    # ---------- results ----------
    def insert_result(self, raw: dict, *, source_url: str = "", retrieved_at: str = "") -> str:
        """Insert a validated result. Returns 'inserted', 'duplicate', or 'conflict'."""
        rec = validate_result(raw)
        if source_url and not rec["source_url"]:
            rec["source_url"] = source_url
        if retrieved_at and not rec["retrieved_at"]:
            rec["retrieved_at"] = retrieved_at
        with self.transaction() as conn:
            existing = conn.execute(
                "SELECT result_number FROM results WHERE period_id=?", (rec["period_id"],)
            ).fetchone()
            if existing:
                return "conflict" if existing["result_number"] != rec["result_number"] else "duplicate"
            conn.execute(
                """INSERT INTO results(period_id,result_number,result_colour,result_size,
                   result_timestamp,source_url,retrieved_at,verification_status,stored_at)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (rec["period_id"], rec["result_number"], rec["result_colour"], rec["result_size"],
                 rec["result_timestamp"], rec["source_url"], rec["retrieved_at"],
                 rec["verification_status"], utcnow()),
            )
        return "inserted"

    def get_result(self, period_id: str) -> dict | None:
        row = self._conn().execute("SELECT * FROM results WHERE period_id=?", (period_id,)).fetchone()
        return dict(row) if row else None

    def get_results(self, limit: int = 200, *, after: str | None = None, before: str | None = None) -> list[dict]:
        sql = "SELECT * FROM results"
        clauses, args = [], []
        if after:
            clauses.append("period_id > ?"); args.append(after)
        if before:
            clauses.append("period_id < ?"); args.append(before)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY period_id DESC LIMIT ?"
        args.append(int(limit))
        return [dict(r) for r in self._conn().execute(sql, args).fetchall()]

    def all_results(self) -> list[dict]:
        return [dict(r) for r in self._conn().execute("SELECT * FROM results ORDER BY period_id ASC")]

    def result_count(self) -> int:
        return int(self._conn().execute("SELECT COUNT(*) FROM results").fetchone()[0])

    def latest_period(self) -> str | None:
        row = self._conn().execute("SELECT MAX(period_id) FROM results").fetchone()
        return row[0] if row and row[0] else None

    # ---------- predictions ----------
    def insert_prediction(self, record: dict) -> str:
        """Insert a draft prediction. Returns 'inserted' or 'duplicate'."""
        with self.transaction() as conn:
            if conn.execute("SELECT 1 FROM predictions WHERE period_id=?", (record["period_id"],)).fetchone():
                return "duplicate"
            conn.execute(
                """INSERT INTO predictions(prediction_id,period_id,created_at,data_cutoff_period,
                   dataset_version,algorithm_version,number_probs,colour_probs,big_prob,small_prob,
                   selected_number,selected_colour,selected_size,sample_count,model_config,
                   prediction_status,is_late,created_after_start_ms)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    record["prediction_id"], record["period_id"], record["created_at"],
                    record["data_cutoff_period"], record["dataset_version"], record["algorithm_version"],
                    json.dumps(record["number_probs"]), json.dumps(record["colour_probs"]),
                    record["big_prob"], record["small_prob"], record["selected_number"],
                    record["selected_colour"], record["selected_size"], record["sample_count"],
                    json.dumps(record["model_config"]), record.get("prediction_status", "draft"),
                    int(record.get("is_late", 0)), record.get("created_after_start_ms"),
                ),
            )
        return "inserted"

    def publish_prediction(self, period_id: str) -> bool:
        """Mark a draft as published. Allowed only once, before evaluation."""
        with self.transaction() as conn:
            cur = conn.execute(
                "UPDATE predictions SET prediction_status='published' WHERE period_id=? AND prediction_status='draft'",
                (period_id,),
            )
            return cur.rowcount == 1

    def get_prediction(self, period_id: str) -> dict | None:
        row = self._conn().execute("SELECT * FROM predictions WHERE period_id=?", (period_id,)).fetchone()
        return self._decode_prediction(row)

    def get_predictions(self, limit: int = 50, *, status: str | None = None) -> list[dict]:
        sql = "SELECT * FROM predictions"
        args: list[Any] = []
        if status:
            sql += " WHERE prediction_status=?"; args.append(status)
        sql += " ORDER BY period_id DESC LIMIT ?"; args.append(int(limit))
        return [p for p in (self._decode_prediction(r) for r in self._conn().execute(sql, args)) if p]

    @staticmethod
    def _decode_prediction(row) -> dict | None:
        if not row:
            return None
        d = dict(row)
        for key in ("number_probs", "colour_probs", "model_config"):
            d[key] = json.loads(d[key])
        return d

    # ---------- evaluations ----------
    def insert_evaluation(self, ev: dict) -> bool:
        with self.transaction() as conn:
            if conn.execute("SELECT 1 FROM evaluations WHERE period_id=?", (ev["period_id"],)).fetchone():
                return False
            conn.execute(
                """INSERT INTO evaluations(prediction_id,period_id,exact_number_hit,colour_hit,size_hit,
                   log_loss,brier_score,baseline_log_loss,baseline_brier,calibration,evaluated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (ev["prediction_id"], ev["period_id"], int(ev["exact_number_hit"]),
                 int(ev["colour_hit"]), int(ev["size_hit"]), ev["log_loss"], ev["brier_score"],
                 ev["baseline_log_loss"], ev["baseline_brier"], json.dumps(ev["calibration"]),
                 ev["evaluated_at"]),
            )
            conn.execute(
                "UPDATE predictions SET prediction_status='evaluated', actual_number=?, evaluated_at=? "
                "WHERE prediction_id=? AND prediction_status='published'",
                (ev["actual_number"], ev["evaluated_at"], ev["prediction_id"]),
            )
        return True

    def get_evaluations(self, limit: int = 200) -> list[dict]:
        rows = self._conn().execute(
            "SELECT * FROM evaluations ORDER BY period_id DESC LIMIT ?", (int(limit),)
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r); d["calibration"] = json.loads(d["calibration"]); out.append(d)
        return out

    # ---------- feed state / events / config ----------
    def get_feed_state(self, key: str) -> dict | None:
        row = self._conn().execute("SELECT * FROM feed_state WHERE feed_key=?", (key,)).fetchone()
        return dict(row) if row else None

    def set_feed_state(self, key: str, **fields) -> None:
        with self.transaction() as conn:
            row = conn.execute("SELECT feed_key FROM feed_state WHERE feed_key=?", (key,)).fetchone()
            if row is None:
                cols = ["feed_key"] + list(fields)
                vals = [key] + list(fields.values())
                conn.execute(f"INSERT INTO feed_state({','.join(cols)}) VALUES({','.join('?'*len(vals))})", vals)
            else:
                cols = ", ".join(f"{k}=?" for k in fields)
                conn.execute(f"UPDATE feed_state SET {cols} WHERE feed_key=?", (*fields.values(), key))

    def log_event(self, level: str, event: str, **details) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO collector_events(ts,level,event,details) VALUES(?,?,?,?)",
                (utcnow(), level, event, json.dumps(details, default=str)),
            )

    def get_events(self, limit: int = 50) -> list[dict]:
        return [dict(r) for r in self._conn().execute(
            "SELECT * FROM collector_events ORDER BY id DESC LIMIT ?", (int(limit),))]

    def get_config(self, key: str, default: str = "") -> str:
        row = self._conn().execute("SELECT value FROM app_config WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_config(self, key: str, value: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO app_config(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def dataset_version(self) -> str:
        rows = self._conn().execute(
            "SELECT period_id,result_number FROM results ORDER BY period_id ASC").fetchall()
        payload = "|".join(f"{r['period_id']}:{r['result_number']}" for r in rows)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    # ---------- integrity / backup / restore ----------
    def integrity_check(self) -> dict:
        conn = self._conn()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = [dict(r) for r in conn.execute("PRAGMA foreign_key_check")]
        gaps = missing_periods(r["period_id"] for r in self.all_results())
        counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in (
            "results", "predictions", "evaluations", "feed_state", "collector_events", "app_config")}
        trigger = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='trigger' AND name='predictions_immutable'").fetchone()
        return {
            "ts": utcnow(), "db": str(self.db_path),
            "integrity": integrity,
            "foreign_key_violations": foreign_keys,
            "counts": counts,
            "missing_periods": gaps,
            "missing_period_count": sum(g[2] for g in gaps),
            "prediction_immutability_trigger": bool(trigger),
            "schema_version": conn.execute(
                "SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0],
            "ok": integrity == "ok" and not foreign_keys and bool(trigger),
        }

    def backup(self, destination: str | Path | None = None) -> Path:
        dest = Path(destination) if destination else self.db_path.with_name(
            f"{self.db_path.stem}_backup_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.sqlite3")
        dest.parent.mkdir(parents=True, exist_ok=True)
        source = sqlite3.connect(str(self.db_path))
        target = sqlite3.connect(str(dest))
        try:
            source.backup(target)  # online, consistent backup (WAL-safe)
        finally:
            target.close(); source.close()
        return dest

    def restore(self, source_file: str | Path, *, force: bool = False) -> dict:
        """Restore from a backup into this store. Always backs up current DB first."""
        src = Path(source_file)
        if not src.is_file():
            raise FileNotFoundError(src)
        current_count = self.result_count()
        if current_count and not force:
            raise ValueError(
                "target database is not empty; call with force=True after creating a backup")
        safety = self.backup()
        # close this thread's connection so the file can be replaced safely
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None
        source = sqlite3.connect(str(src))
        target = sqlite3.connect(str(self.db_path))
        try:
            source.backup(target)
        finally:
            target.close(); source.close()
        return {"restored_from": str(src), "safety_backup": str(safety),
                "results_before": current_count, "results_after": self.result_count()}


def validate_import_rows(rows: Iterable[dict]) -> tuple[list[dict], list[str]]:
    valid, errors = [], []
    for i, raw in enumerate(rows, 1):
        try:
            valid.append(validate_result(raw))
        except ValidationError as exc:
            errors.append(f"row {i}: {exc}")
    return valid, errors
