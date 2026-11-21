"""Full collector pipeline tests using injected fake HTTP transport."""
import json
import unittest

from hmx.collector import collect_once
from hmx.engine import EngineConfig
from hmx.logging_util import JsonLogger
from hmx.providers.http import FeedClient, HttpResponse
from hmx.providers.wingo_public import WingoPublicProvider
from hmx.scheduler import PeriodTracker
from tests.common import PHASE0_CSV, temp_store
from hmx.importer import import_file


def ok(body, etag="E1"):
    return HttpResponse(200, {"ETag": etag}, json.dumps(body).encode())


KV = {"code": 0, "data": {"startTime": 1795235880000, "endTime": 1795235940000,
      "issueNumber": "20261121100010341", "intervalMinute": 60, "gameCode": "WinGo_1M",
      "countdown": 30}, "msg": "Succeed"}
SCHED = {"gameCode": "WinGo_1M", "intervalMinute": 1.0, "state": 1,
         "current": {"issueNumber": "20261121100010341", "startTime": 1795235880000, "endTime": 1795235940000},
         "next": {"issueNumber": "20261121100010342", "startTime": 1795235940000, "endTime": 1795236000000}}
HIST = {"code": 0, "data": {"list": [
    {"issueNumber": "20261121100010340", "number": "3", "color": "green", "premium": "3", "sum": 0},
    {"issueNumber": "20261121100010339", "number": "2", "color": "red", "premium": "2", "sum": 0},
], "pageNo": 1, "totalPage": 50, "totalCount": 500}}


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
    def request(self, url, headers=None, timeout=15.0):
        return self.responses.pop(0)


class CollectorPipelineTests(unittest.TestCase):
    def setUp(self):
        self.store, self.tmp = temp_store()
        import_file(self.store, PHASE0_CSV)
        self.logger = JsonLogger(__import__('pathlib').Path(self.tmp.name) / "c.jsonl", "test")

    def tearDown(self):
        self.tmp.cleanup()

    def make_provider(self, responses):
        client = FeedClient(FakeTransport(responses), min_interval=0, max_retries=0, logger=self.logger)
        return WingoPublicProvider(client, kv_url="u1", schedule_url="u2", history_url="u3")

    def test_full_cycle_inserts_predicts_reconciles(self):
        hist2 = {"code": 0, "data": {"list": [
            {"issueNumber": "20261121100010341", "number": "6", "color": "red", "premium": "6", "sum": 0},
            {"issueNumber": "20261121100010340", "number": "3", "color": "green", "premium": "3", "sum": 0},
        ], "pageNo": 1, "totalPage": 50, "totalCount": 500}}
        provider = self.make_provider([
            ok(KV, "k1"), ok(SCHED, "s1"), ok(HIST, "h1"),
            ok(KV, "k1"), ok(SCHED, "s1"), ok(hist2, "h2"),
        ])
        tracker = PeriodTracker(self.store, EngineConfig(min_history=10, analysis_window=100))
        first = collect_once(provider, self.store, tracker, self.logger)
        self.assertEqual(first["statuses"], {"kv_issue": "ok", "schedule": "ok", "history": "ok"})
        self.assertEqual(len(first["new_results"]), 2)
        self.assertEqual(self.store.result_count(), 48)
        self.assertEqual(len(self.store.get_predictions(10)), 1)
        self.assertEqual(len(self.store.get_evaluations(10)), 0)
        self.assertEqual(self.store.get_feed_state("history")["etag"], "h1")

        second = collect_once(provider, self.store, tracker, self.logger)
        self.assertEqual(second["new_results"], ["20261121100010341"])
        self.assertEqual(len(self.store.get_evaluations(10)), 1)
        self.assertEqual(self.store.get_prediction("20261121100010341")["prediction_status"], "evaluated")

    def test_304_and_duplicates_are_noops(self):
        provider = self.make_provider([
            ok(KV, "k1"), ok(SCHED, "s1"), ok(HIST, "h1"),
            ok(KV, "k1"), ok(SCHED, "s1"),
            HttpResponse(304, {"ETag": "h1"}, b""),
        ])
        tracker = PeriodTracker(self.store, EngineConfig(min_history=10, analysis_window=100))
        collect_once(provider, self.store, tracker, self.logger)
        second = collect_once(provider, self.store, tracker, self.logger)
        self.assertEqual(second["statuses"]["history"], "not_modified")
        self.assertEqual(self.store.result_count(), 48)
        self.assertEqual(len(self.store.get_predictions(10)), 1)

    def test_schema_error_does_not_corrupt_store(self):
        bad = {"code": 0, "data": {"list": [{"issueNumber": "bad", "number": 99}]}}
        provider = self.make_provider([ok(KV), ok(SCHED), ok(bad)])
        tracker = PeriodTracker(self.store, EngineConfig(min_history=10))
        result = collect_once(provider, self.store, tracker, self.logger)
        self.assertEqual(result["statuses"]["history"], "schema_error")
        self.assertEqual(self.store.result_count(), 46)


if __name__ == "__main__":
    unittest.main()
