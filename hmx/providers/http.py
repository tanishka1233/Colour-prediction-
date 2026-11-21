"""HTTP transport and ETag-aware conditional GET client (stdlib only)."""
from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Protocol

from ..logging_util import utcnow


@dataclass
class HttpResponse:
    status: int
    headers: dict
    body: bytes = b""


class Transport(Protocol):
    def request(self, url: str, headers: dict | None = None, timeout: float = 15.0) -> HttpResponse: ...


class UrllibTransport:
    """Real HTTP GET. Sends no cookies, no Authorization header."""

    def request(self, url: str, headers: dict | None = None, timeout: float = 15.0) -> HttpResponse:
        req = urllib.request.Request(url, headers=headers or {}, method="GET")
        req.add_header("User-Agent", "HMX-Predictor/1.0 (read-only research)")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return HttpResponse(resp.status, dict(resp.headers), resp.read())
        except urllib.error.HTTPError as exc:
            return HttpResponse(exc.code, dict(exc.headers), exc.read())


@dataclass
class FeedResult:
    key: str
    url: str
    status: str                 # ok | not_modified | throttled | error
    data: dict | list | None = None
    etag: str | None = None
    last_modified: str | None = None
    http_status: int | None = None
    error: str | None = None
    attempted: bool = False


class FeedClient:
    """Conditional GET with per-feed throttling and exponential backoff.

    - Maximum one request per minute per feed (configurable, never below 60 s in production).
    - ETag / If-None-Match support; HTTP 304 returns status='not_modified'.
    - Retries transient failures with exponential backoff + jitter.
    - Injectable transport, clock and sleeper for deterministic tests.
    """

    def __init__(
        self,
        transport: Transport | None = None,
        *,
        min_interval: float = 60.0,
        timeout: float = 15.0,
        max_retries: int = 4,
        backoff_base: float = 2.0,
        backoff_cap: float = 120.0,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
        logger=None,
    ):
        self.transport = transport or UrllibTransport()
        self.min_interval = float(min_interval)
        self.timeout = float(timeout)
        self.max_retries = int(max_retries)
        self.backoff_base = float(backoff_base)
        self.backoff_cap = float(backoff_cap)
        self._clock = clock or time.monotonic
        self._sleeper = sleeper or time.sleep
        self.logger = logger
        self._state: dict[str, dict] = {}

    def seed(self, key: str, *, etag: str | None = None, last_request_epoch: float | None = None) -> None:
        """Restore ETag and throttle window after an application restart."""
        state = self._state.setdefault(key, {"etag": None, "last": None, "failures": 0})
        if etag:
            state["etag"] = etag
        if last_request_epoch:
            elapsed = time.time() - float(last_request_epoch)
            state["last"] = self._clock() - elapsed if elapsed >= 0 else None

    def get(self, key: str, url: str) -> FeedResult:
        state = self._state.setdefault(key, {"etag": None, "last": None, "failures": 0,
                                             "last_epoch": None})
        now = self._clock()
        last = state.get("last")
        if last is not None and (now - last) < self.min_interval:
            return FeedResult(key, url, "throttled", http_status=None)

        headers = {"Accept": "application/json, */*"}
        if state["etag"]:
            headers["If-None-Match"] = state["etag"]

        response = None
        error = None
        for attempt in range(self.max_retries + 1):
            state["last"] = self._clock()
            state["last_epoch"] = time.time()
            try:
                response = self.transport.request(url, headers=headers, timeout=self.timeout)
            except Exception as exc:  # network failure
                error = f"{type(exc).__name__}: {exc}"
            else:
                if response.status in (200, 304):
                    error = None
                    break
                if response.status == 429:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after and retry_after.isdigit() else self._delay(attempt)
                elif 500 <= response.status < 600:
                    delay = self._delay(attempt)
                else:
                    return FeedResult(key, url, "error", http_status=response.status,
                                      error=f"HTTP {response.status}", attempted=True)
                error = f"HTTP {response.status}"
                if attempt < self.max_retries:
                    self._sleeper(delay)
                    continue
            if attempt < self.max_retries:
                self._sleeper(self._delay(attempt))
        if error:
            state["failures"] += 1
            if self.logger:
                self.logger.warn("feed_failure", feed=key, error=error, failures=state["failures"])
            return FeedResult(key, url, "error", http_status=response.status if response else None,
                              error=error, attempted=True)

        assert response is not None
        state["failures"] = 0
        state["etag"] = response.headers.get("ETag") or response.headers.get("etag") or state["etag"]
        common = dict(key=key, url=url, etag=state["etag"],
                      last_modified=response.headers.get("Last-Modified") or response.headers.get("last-modified"),
                      http_status=response.status, attempted=True)
        if response.status == 304:
            return FeedResult(status="not_modified", **common)
        try:
            data = json.loads(response.body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            state["failures"] += 1
            return FeedResult(status="error", error=f"invalid JSON: {exc}", **common)
        if not isinstance(data, (dict, list)):
            return FeedResult(status="error", error="JSON root must be object or array", **common)
        return FeedResult(status="ok", data=data, **common)

    def _delay(self, attempt: int) -> float:
        base = min(self.backoff_cap, self.backoff_base * (2 ** attempt))
        return base * (0.8 + 0.4 * random.random())

    def snapshot(self, key: str) -> dict | None:
        return self._state.get(key)
