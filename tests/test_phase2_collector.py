"""Phase 2: historical collection summary, ETag recovery and failure resilience."""
import json
import tempfile
import unittest
from pathlib import Path

from hmx.collector import collect_history_once
from hmx.db import Store
from hmx.logging_util import JsonLogger
from hmx.providers.http import FeedClient, HttpResponse, Transport
from hmx.providers.wingo_public import WingoPublicProvider
from tests.common import PHASE0_CSV
from hmx.importer import import_file


HIST = {"code": 0, "data": {"list": [
    {"issueNumber": "20261121100010338", "number": "1", "color": "green", "premium": "1", "sum": 0},
    {"issueNumber": "20261121100010337", "number": "7", "color": "green", "premium": "7", "sum": 0},
], "pageNo": 1, "totalPage": 50, "totalCount": 500}}


class ScriptedTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def request(self, url, headers=None, timeout=15.0):
        self.calls += 1
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class Phase2CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.store = Store(self.base / "main.sqlite3")
        self.logger = JsonLogger(self.base / "collector.jsonl", "test")

    def tearDown(self):
        self.tmp.cleanup()

    def provider(self, responses, min_interval=0):
        client = FeedClient(ScriptedTransport(responses), min_interval=min_interval,
                            max_retries=1, logger=self.logger)
        return client, WingoPublicProvider(client, kv_url="u1", schedule_url="u2", history_url="u3")

    def test_history_summary_insert_duplicate_and_limitation(self):
        ok1 = HttpResponse(200, {"ETag": "H1"}, json.dumps(HIST).encode())
        client, provider = self.provider([ok1])
        first = collect_history_once(provider, self.store, self.logger)
        self.assertEqual(first["snapshot_count"], 2)
        self.assertEqual(first["inserted"], 2)
        self.assertEqual(first["total_stored"], 2)
        self.assertIn("latest 10", first["limitation"])
        # second call with same ETag -> 304, no duplicates
        client.seed("history", etag="H1")
        client2, provider2 = self.provider([HttpResponse(304, {"ETag": "H1"}, b"")])
        second = collect_history_once(provider2, self.store, self.logger)
        self.assertEqual(second["feed_status"], "not_modified")
        self.assertEqual(second["duplicate"], 0)
        self.assertEqual(self.store.result_count(), 2)

    def test_history_schema_error_is_reported_not_crashed(self):
        bad = {"code": 0, "data": {"list": [{"issueNumber": "bad", "number": 99}]}}
        _, provider = self.provider([HttpResponse(200, {}, json.dumps(bad).encode())])
        summary = collect_history_once(provider, self.store, self.logger)
        self.assertTrue(summary["errors"])
        self.assertEqual(self.store.result_count(), 0)

    def test_etag_and_throttle_recovered_after_restart(self):
        client, _ = self.provider([], min_interval=60)
        client.seed("history", etag="ETAG-1", last_request_epoch=__import__('time').time())
        result = client.get("history", "u3")
        self.assertEqual(result.status, "throttled")
        self.assertEqual(client.snapshot("history")["etag"], "ETAG-1")

    def test_network_failure_retries_then_recovers(self):
        slept = []
        client = FeedClient(ScriptedTransport([OSError("offline"),
                        HttpResponse(200, {}, json.dumps(HIST).encode())]),
                            min_interval=0, max_retries=2, sleeper=lambda s: slept.append(s))
        result = client.get("history", "u3")
        self.assertEqual(result.status, "ok")
        self.assertEqual(len(slept), 1)


if __name__ == "__main__":
    unittest.main()
