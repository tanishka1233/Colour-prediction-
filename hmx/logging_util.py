"""Structured JSON-line logging."""
from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

_LOCK = threading.Lock()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class JsonLogger:
    def __init__(self, path: Path, component: str):
        self.path = path
        self.component = component
        path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, level: str, event: str, **fields) -> None:
        record = {"ts": utcnow(), "level": level, "component": self.component,
                  "event": event, **fields}
        line = json.dumps(record, ensure_ascii=False, default=str)
        with _LOCK:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
            sys.stderr.write(line + "\n")

    def info(self, event: str, **fields) -> None:
        self.log("INFO", event, **fields)

    def warn(self, event: str, **fields) -> None:
        self.log("WARN", event, **fields)

    def error(self, event: str, **fields) -> None:
        self.log("ERROR", event, **fields)
