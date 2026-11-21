"""Configuration. No credentials are used or stored by this application.

All external result access is read-only and isolated in hmx.providers.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Config:
    # Paths
    root: Path = ROOT
    data_dir: Path = field(default_factory=lambda: Path(_env("HMX_DATA_DIR", str(ROOT / "data"))))
    log_dir: Path = field(default_factory=lambda: Path(_env("HMX_LOG_DIR", str(ROOT / "logs"))))
    db_path: Path = field(default_factory=lambda: Path(_env("HMX_DB_PATH", str(ROOT / "data" / "hmx.sqlite3"))))

    # Public provider (undocumented, unauthenticated, read-only feeds)
    kv_issue_url: str = _env("HMX_KV_ISSUE_URL", "https://maanwin29.com/webapi/kv/issue/WinGo_1M")
    schedule_url: str = _env("HMX_SCHEDULE_URL", "https://draw.ar-lottery01.com/WinGo/WinGo_1M.json")
    history_url: str = _env(
        "HMX_HISTORY_URL",
        "https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json",
    )
    game_code: str = _env("HMX_GAME_CODE", "WinGo_1M")
    lottery_code: str = _env("HMX_LOTTERY_CODE", "WinGo")

    # Collector behaviour
    poll_interval_seconds: int = max(60, _env_int("HMX_POLL_INTERVAL_SECONDS", 60))
    request_timeout_seconds: float = _env_float("HMX_REQUEST_TIMEOUT_SECONDS", 15.0)
    max_retries: int = _env_int("HMX_MAX_RETRIES", 4)
    backoff_base_seconds: float = _env_float("HMX_BACKOFF_BASE_SECONDS", 2.0)
    backoff_cap_seconds: float = _env_float("HMX_BACKOFF_CAP_SECONDS", 120.0)
    collector_autostart: bool = _env("HMX_COLLECTOR_AUTOSTART", "0") == "1"
    provider_enabled: bool = _env("HMX_PROVIDER_ENABLED", "1") == "1"

    # HTTP server
    host: str = _env("HMX_HOST", "127.0.0.1")
    port: int = _env_int("HMX_PORT", 8765)
    rate_limit_per_minute: int = _env_int("HMX_RATE_LIMIT_PER_MINUTE", 120)

    # Engine defaults (can be overridden per prediction via config JSON)
    min_history: int = _env_int("HMX_MIN_HISTORY", 30)
    analysis_window: int = _env_int("HMX_ANALYSIS_WINDOW", 200)
    recency_tau: float = _env_float("HMX_RECENCY_TAU", 40.0)
    dirichlet_alpha: float = _env_float("HMX_DIRICHLET_ALPHA", 1.0)
    engine_weights: dict = field(default_factory=lambda: {
        "frequency": 0.30,
        "recency": 0.30,
        "transition": 0.20,
        "bayesian": 0.20,
    })

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


CONFIG = Config()
