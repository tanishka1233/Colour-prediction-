"""Stdlib HTTP API + static mobile frontend server."""
from __future__ import annotations

import json
import mimetypes
import time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import __version__
from .collector import Collector
from .config import CONFIG, Config
from .db import Store
from .engine import EngineConfig
from .evaluation import evaluation_report, summarize, walk_forward
from .importer import export_csv, export_json, import_rows, parse_csv, parse_json
from .logging_util import JsonLogger, utcnow
from .rules import missing_periods
from .scheduler import PeriodTracker

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class RateLimiter:
    def __init__(self, limit: int, window: float = 60.0):
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        q = self._hits[key]
        while q and q[0] <= now - self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True


class AppState:
    def __init__(self, config: Config | None = None):
        self.config = config or CONFIG
        self.config.ensure_dirs()
        self.store = Store(self.config.db_path)
        self.logger = JsonLogger(self.config.log_dir / "server.jsonl", "server")
        self.engine_config = EngineConfig.from_dict({
            "min_history": self.config.min_history,
            "analysis_window": self.config.analysis_window,
            "recency_tau": self.config.recency_tau,
            "dirichlet_alpha": self.config.dirichlet_alpha,
            "weights": self.config.engine_weights,
        })
        self.engine_config_json = self.engine_config.to_dict()
        self.tracker = PeriodTracker(self.store, self.engine_config)
        self.collector = Collector(self.config, self.store, scheduler=self.tracker,
                                   logger=JsonLogger(self.config.log_dir / "collector.jsonl", "collector"))
        self.limiter = RateLimiter(self.config.rate_limit_per_minute)
        if self.config.collector_autostart:
            self.collector.start()

    def shutdown(self) -> None:
        self.collector.stop()
        self.logger.info("server_shutdown")


class Handler(BaseHTTPRequestHandler):
    state: AppState
    server_version = "HMXPredictor/1.0"

    # ---- helpers ----
    def _send(self, status: int, body: bytes, content_type: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, status: int = 200) -> None:
        self._send(status, json.dumps(obj, ensure_ascii=False, default=str).encode(),
                   "application/json; charset=utf-8")

    def _error(self, status: int, message: str) -> None:
        self._json({"error": message, "ts": utcnow()}, status)

    def _read_body(self, limit: int = 2_000_000) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > limit:
            raise ValueError("invalid Content-Length")
        return self.rfile.read(length)

    def _client(self) -> str:
        return self.client_address[0] if self.client_address else "unknown"

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        if not self.state.limiter.allow(self._client()):
            return self._error(429, "rate limit exceeded")
        try:
            return self._get(path, query)
        except Exception as exc:
            self.state.logger.error("request_failed", path=path, error=str(exc))
            return self._error(500, "internal error")

    def _get(self, path: str, query: dict) -> None:
        store = self.state.store
        if path in ("/", "/index.html"):
            return self._static(WEB_DIR / "index.html")
        if path in ("/app.js", "/styles.css", "/favicon.ico"):
            return self._static(WEB_DIR / path.lstrip("/"))
        if path == "/api/health":
            return self._json({"status": "ok", "version": __version__, "ts": utcnow(),
                               "results": store.result_count(),
                               "predictions": len(store.get_predictions(1)),
                               "collector": self.state.collector.health()["running"]})
        if path == "/api/status":
            return self._json({
                "app": "HMX Predictor", "version": __version__, "ts": utcnow(),
                "game_code": self.state.config.game_code,
                "provider_enabled": self.state.config.provider_enabled,
                "poll_interval_seconds": self.state.config.poll_interval_seconds,
                "collector": self.state.collector.health(),
                "results": store.result_count(),
                "predictions": len(store.get_predictions(1000)),
                "feed_state": [dict(r) for r in store._conn().execute("SELECT * FROM feed_state")],
                "events": store.get_events(10),
                "source_note": "Undocumented public feeds; read-only. Not for commercial use without authorization.",
            })
        if path == "/api/results":
            limit = min(1000, int(query.get("limit", ["200"])[0]))
            rows = store.get_results(limit)
            return self._json({"count": len(rows), "results": rows,
                               "missing_periods": missing_periods(r["period_id"] for r in rows)})
        if path == "/api/predictions":
            limit = min(500, int(query.get("limit", ["50"])[0]))
            return self._json({"predictions": store.get_predictions(limit)})
        if path == "/api/evaluations":
            limit = min(1000, int(query.get("limit", ["200"])[0]))
            return self._json({"evaluations": store.get_evaluations(limit)})
        if path == "/api/stats":
            rows = store.all_results()
            from collections import Counter
            numbers = Counter(r["result_number"] for r in rows)
            colours = Counter(r["result_colour"] for r in rows)
            sizes = Counter(r["result_size"] for r in rows)
            seq = [r["result_number"] for r in rows]
            repeats = sum(1 for a, b in zip(seq, seq[1:]) if a == b)
            evaluated = store.get_evaluations(1000)
            predictions = store.get_predictions(1000)
            report = evaluation_report(
                predictions, evaluated,
                walk_forward_summary=summarize(walk_forward(rows)))
            report["sample_size"] = len(rows)
            report["missing_count"] = sum(g[2] for g in missing_periods(r["period_id"] for r in rows))
            report["number_counts"] = {str(i): numbers.get(i, 0) for i in range(10)}
            report["colour_counts"] = dict(colours)
            report["size_counts"] = dict(sizes)
            report["consecutive_repeats"] = repeats
            report["accuracy"] = summarize(evaluated)
            report["note"] = "Descriptive statistics only. Past frequency does not predict future results."
            return self._json(report)
        if path == "/api/config":
            return self._json({"analysis_window": int(store.get_config("analysis_window", "200")),
                               "engine": self.state.engine_config_json,
                               "display_timezone": "local (browser)"})
        if path == "/api/export":
            fmt = query.get("format", ["csv"])[0]
            rows = store.all_results()
            if fmt == "json":
                return self._send(200, export_json(rows).encode(), "application/json")
            return self._send(200, export_csv(rows).encode(), "text/csv; charset=utf-8",
                              {"Content-Disposition": 'attachment; filename="hmx_results.csv"'})
        if path == "/api/collector/once":
            result = self.state.collector.run_once()
            return self._json(result)
        return self._error(404, "not found")

    def _static(self, path: Path) -> None:
        if not path.is_file() or WEB_DIR not in path.resolve().parents and path.resolve() != WEB_DIR:
            return self._error(404, "not found")
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self._send(200, path.read_bytes(), ctype)

    def do_POST(self):
        if not self.state.limiter.allow(self._client()):
            return self._error(429, "rate limit exceeded")
        path = urlparse(self.path).path
        try:
            body = self._read_body()
            if path == "/api/backup":
                return self._json({"backup": str(self.state.store.backup())})
            if path == "/api/collector/start":
                self.state.collector.start()
                return self._json({"running": self.state.collector.health()["running"]})
            if path == "/api/collector/stop":
                self.state.collector.stop()
                return self._json({"running": False})
            if path == "/api/import":
                try:
                    payload = json.loads(body.decode())
                except (ValueError, UnicodeDecodeError):
                    return self._error(400, "invalid JSON")
                rows = payload.get("rows")
                if not isinstance(rows, list) and isinstance(payload.get("text"), str):
                    text = payload["text"]
                    fmt = str(payload.get("format", "csv")).lower()
                    rows = parse_json(text) if fmt == "json" else parse_csv(text)
                if not isinstance(rows, list):
                    text = body.decode("utf-8", errors="replace")
                    rows = parse_json(text) if text.lstrip().startswith("[") or '"records"' in text else parse_csv(text)
                stats = import_rows(self.state.store, rows)
                self.state.logger.info("csv_import", **{k: v for k, v in stats.items() if k != "errors"})
                return self._json(stats)
            if path == "/api/config":
                payload = json.loads(body.decode())
                if "analysis_window" in payload:
                    value = max(10, min(5000, int(payload["analysis_window"])))
                    self.state.store.set_config("analysis_window", str(value))
                    return self._json({"analysis_window": value})
                return self._error(400, "no supported setting")
            return self._error(404, "not found")
        except ValueError as exc:
            return self._error(400, str(exc))
        except Exception as exc:
            self.state.logger.error("request_failed", path=path, error=str(exc))
            return self._error(500, "internal error")

    def log_message(self, fmt, *args):  # keep structured logs only
        pass


def serve(config: Config | None = None) -> None:
    state = AppState(config)
    server = ThreadingHTTPServer((state.config.host, state.config.port), Handler)
    Handler.state = state
    try:
        state.logger.info("server_started", host=state.config.host, port=state.config.port)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        state.shutdown()
