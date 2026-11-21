"""Phase 2: late prediction marking, leakage guard, evaluation coverage."""
import tempfile
import unittest
from pathlib import Path

from hmx.db import Store
from hmx.engine import EngineConfig
from hmx.evaluation import evaluation_report, summarize, walk_forward
from hmx.importer import import_file
from hmx.providers.wingo_public import PeriodState
from hmx.scheduler import PeriodTracker
from tests.common import PHASE0_CSV, synthetic_result


def state(seq4, start=1795235880000):
    return PeriodState(f"2026112110001{seq4:04d}", start, start + 60000, 30)


class Phase2LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "main.sqlite3")
        import_file(self.store, PHASE0_CSV)
        self.config = EngineConfig(min_history=10, analysis_window=100)

    def tearDown(self):
        self.tmp.cleanup()

    def test_late_prediction_marked_and_excluded_from_accuracy(self):
        tracker = PeriodTracker(self.store, self.config, late_prediction_seconds=30)
        # now is 100 s after period start -> late prediction
        created = tracker.observe(state(340, start=1795235880000), None,
                                  now_ms=1795235980000)
        self.assertEqual(len(created), 1)
        p = self.store.get_prediction("20261121100010340")
        self.assertEqual(p["is_late"], 1)
        self.assertGreaterEqual(p["created_after_start_ms"], 100000)

        result = synthetic_result("20261121100010340", 3)
        self.store.insert_result(result)
        ev = tracker.reconcile([result], now_ms=1795236040000)
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["late"], 1)
        self.assertEqual(summarize([ev[0]])["count"], 0)          # excluded
        self.assertEqual(summarize([ev[0]], include_late=True)["count"], 1)

    def test_no_late_prediction_when_created_at_start(self):
        tracker = PeriodTracker(self.store, self.config, late_prediction_seconds=30)
        tracker.observe(state(341, start=1795235940000), None, now_ms=1795235940000)
        p = self.store.get_prediction("20261121100010341")
        self.assertEqual(p["is_late"], 0)

    def test_no_duplicate_predictions_and_no_future_data(self):
        tracker = PeriodTracker(self.store, self.config)
        a = tracker.observe(state(342, start=1795236000000), None, now_ms=1795236000000)
        b = tracker.observe(state(342, start=1795236000000), None, now_ms=1795236010000)
        self.assertEqual(len(a), 1)
        self.assertEqual(b, [])
        cutoff = a[0]["data_cutoff_period"]
        self.assertLessEqual(cutoff, "20261121100010337")

    def test_evaluation_report_fields(self):
        tracker = PeriodTracker(self.store, self.config)
        tracker.observe(state(343, start=1795236060000), None, now_ms=1795236060000)
        result = synthetic_result("20261121100010343", 2)
        self.store.insert_result(result)
        tracker.reconcile([result], now_ms=1795236120000)
        report = evaluation_report(self.store.get_predictions(100),
                                   self.store.get_evaluations(100),
                                   walk_forward_summary=summarize(walk_forward(self.store.all_results())))
        for key in ("total_predictions", "evaluated_predictions", "pending_predictions",
                    "late_predictions_created", "late_evaluations_excluded",
                    "exact_accuracy", "mean_log_loss", "mean_brier",
                    "baseline_log_loss", "baseline_brier", "calibration",
                    "walk_forward", "disclaimer"):
            self.assertIn(key, report)
        self.assertTrue(report["insufficient_data"])


if __name__ == "__main__":
    unittest.main()
