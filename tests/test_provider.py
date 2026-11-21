import json
import unittest

from hmx.logging_util import JsonLogger
from hmx.providers.http import FeedClient, HttpResponse, FeedResult
from hmx.providers.wingo_public import (
    SchemaError, WingoPublicProvider, parse_history, parse_kv_issue, parse_schedule,
)

KV = {"code": 0, "data": {"startTime": 1795235880000, "endTime": 1795235940000,
      "issueNumber": "20261121100010279", "intervalMinute": 60, "gameCode": "WinGo_1M",
      "diif": 0, "countdown": 28}, "msg": "Succeed", "msgCode": 0, "serverTime": 1795235911274}

SCHEDULE = {"gameCode": "WinGo_1M", "intervalMinute": 1.0, "state": 1,
            "previous": {"issueNumber": "20261121100010278", "startTime": 1795235820000, "endTime": 1795235880000},
            "current": {"issueNumber": "20261121100010279", "startTime": 1795235880000, "endTime": 1795235940000},
            "next": {"issueNumber": "20261121100010280", "startTime": 1795235940000, "endTime": 1795236000000}}

HISTORY = {"data": {"list": [
    {"issueNumber": "20261121100010278", "number": "5", "color": "green,violet", "premium": "5", "sum": 0},
    {"issueNumber": "20261121100010277", "number": "8", "color": "red", "premium": "8", "sum": 0},
], "pageNo": 1, "totalPage": 50, "totalCount": 500}, "code": 0, "msg": "Succeed"}


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, url, headers=None, timeout=15.0):
        self.calls.append((url, dict(headers or {})))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def ok(body, etag="E1"):
    return HttpResponse(200, {"ETag": etag, "Last-Modified": "Sat, 21 Nov 2026 04:38:57 GMT"},
                        json.dumps(body).encode())


class ParserTests(unittest.TestCase):
    def test_kv_schema(self):
        state = parse_kv_issue(KV)
        self.assertEqual(state.issue_number, "20261121100010279")
        self.assertEqual(state.end_ms - state.start_ms, 60000)
        self.assertEqual(state.countdown, 28)

    def test_schedule_schema(self):
        s = parse_schedule(SCHEDULE)
        self.assertEqual(s.current.issue_number, "20261121100010279")
        self.assertEqual(s.next.issue_number, "20261121100010280")

    def test_history_schema_and_derived_timestamp(self):
        rows = parse_history(HISTORY, source_url="https://example.invalid/h.json", retrieved_at="2026-11-21T04:39:00+00:00")
        self.assertEqual(rows[0]["result_number"], 5)
        self.assertEqual(rows[0]["result_colour"], "green,violet")
        self.assertEqual(rows[0]["result_timestamp"], "2026-11-21T04:38:00Z")
        self.assertEqual(rows[0]["source_url"], "https://example.invalid/h.json")

    def test_bad_schema(self):
        with self.assertRaises(SchemaError):
            parse_kv_issue({"code": 1, "data": {}})
        with self.assertRaises(SchemaError):
            parse_history({"code": 0, "data": {"list": [{"issueNumber": "x", "number": 3}]}})


class FeedClientTests(unittest.TestCase):
    def setUp(self):
        self.t = 0.0
        self.slept = []
        self.clock = lambda: self.t
        self.sleeper = lambda s: self.slept.append(s)

    def client(self, responses, min_interval=60.0):
        return FeedClient(FakeTransport(responses), min_interval=min_interval, clock=self.clock,
                          sleeper=self.sleeper, max_retries=2, backoff_base=1.0)

    def test_etag_and_304(self):
        c = self.client([ok({"a": 1}, "E1"), HttpResponse(304, {"ETag": "E1"}, b"")])
        first = c.get("history", "https://example.invalid/h.json")
        self.assertEqual(first.status, "ok")
        second = c.get("history", "https://example.invalid/h.json")  # throttled
        self.assertEqual(second.status, "throttled")
        self.t = 61.0
        third = c.get("history", "https://example.invalid/h.json")
        self.assertEqual(third.status, "not_modified")
        self.assertEqual(c.transport.calls[1][1].get("If-None-Match"), "E1")

    def test_transient_failure_backoff(self):
        c = self.client([OSError("offline"), OSError("offline"), ok({"ok": True})])
        r = c.get("schedule", "https://example.invalid/s.json")
        self.assertEqual(r.status, "ok")
        self.assertEqual(len(self.slept), 2)

    def test_http_4xx_is_not_retried(self):
        c = self.client([HttpResponse(403, {}, b""), ok({"ok": True})])
        r = c.get("schedule", "https://example.invalid/s.json")
        self.assertEqual(r.status, "error")
        self.assertEqual(r.http_status, 403)


class ProviderTests(unittest.TestCase):
    def test_provider_uses_three_distinct_urls(self):
        transport = FakeTransport([ok({"ok": 1}), ok({"ok": 2}), ok({"ok": 3})])
        client = FeedClient(transport, min_interval=0)
        p = WingoPublicProvider(client, kv_url="u1", schedule_url="u2", history_url="u3")
        p.current_issue(); p.schedule(); p.history()
        self.assertEqual([c[0] for c in transport.calls], ["u1", "u2", "u3"])


if __name__ == "__main__":
    unittest.main()
