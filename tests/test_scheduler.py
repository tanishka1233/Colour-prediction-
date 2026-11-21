import unittest

from hmx.engine import EngineConfig
from hmx.providers.wingo_public import PeriodState
from hmx.scheduler import PeriodTracker
from tests.common import PHASE0_CSV, synthetic_result, temp_store
from hmx.importer import import_file


def state(seq4: int) -> PeriodState:
    """seq4 = the 4-digit period suffix (e.g. 340 -> ...10340)."""
    start = 1795235880000 + (seq4 - 279) * 60000
    return PeriodState(f"2026112110001{seq4:04d}", start, start + 60000, 30)


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.store, self.tmp = temp_store()
        import_file(self.store, PHASE0_CSV)
        self.config = EngineConfig(min_history=10, analysis_window=100)

    def tearDown(self):
        self.tmp.cleanup()

    def test_one_prediction_per_period_and_transition(self):
        tracker = PeriodTracker(self.store, self.config)
        first = tracker.observe(state(338), None, now_ms=1795235940000)
        second = tracker.observe(state(338), None, now_ms=1795235945000)
        third = tracker.observe(state(339), None, now_ms=1795236000000)
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])
        self.assertEqual(len(third), 1)
        self.assertEqual(len(tracker.transitions), 2)
        self.assertEqual(len(self.store.get_predictions(50)), 2)
        self.assertEqual(first[0]["data_cutoff_period"], "20261121100010337")

    def test_no_prediction_when_result_already_known(self):
        self.store.insert_result(synthetic_result("20261121100010340", 4))
        tracker = PeriodTracker(self.store, self.config)
        created = tracker.observe(state(340), None, now_ms=1)
        self.assertEqual(created, [])
        self.assertEqual(self.store.get_prediction("20261121100010340"), None)

    def test_reconcile_evaluates_and_detects_late(self):
        tracker = PeriodTracker(self.store, self.config)
        created = tracker.observe(state(340), None, now_ms=1795236000000)
        self.assertEqual(len(created), 1)
        result = synthetic_result("20261121100010340", 7)
        self.store.insert_result(result)
        ev = tracker.reconcile([result], now_ms=1795236060000)
        self.assertEqual(len(ev), 1)
        self.assertEqual(self.store.get_prediction("20261121100010340")["prediction_status"], "evaluated")
        # repeated reconciliation is idempotent
        self.assertEqual(tracker.reconcile([result], now_ms=1795236060000), [])

    def test_no_guessed_future_ids(self):
        tracker = PeriodTracker(self.store, self.config)
        tracker.observe(state(340), None, now_ms=1)
        self.assertEqual(tracker.current_period, "20261121100010340")
        self.assertNotIn("20261121100010341", tracker.seen)
        self.assertEqual(len(self.store.get_predictions(50)), 1)


if __name__ == "__main__":
    unittest.main()
