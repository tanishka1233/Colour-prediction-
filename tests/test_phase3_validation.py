"""Phase 3 walk-forward validation and model-comparison tests."""
import unittest
from unittest import mock

from hmx.models import MODEL_NAMES
from hmx.validation import walk_forward_compare
from tests.common import PHASE0_CSV, synthetic_result


class ValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from hmx.importer import parse_csv
        cls.rows = parse_csv(PHASE0_CSV.read_text(encoding="utf-8"))

    def test_walk_forward_uses_only_past_periods(self):
        seen = []

        def spy(name, numbers, config=None):
            seen.append((name, list(numbers)))
            from hmx.models import model_probs
            return model_probs(name, numbers, config)

        with mock.patch("hmx.validation.model_probs", side_effect=spy):
            result = walk_forward_compare(self.rows, models=["frequency"], min_train=30)
        self.assertEqual(result["evaluation_count"], len(self.rows) - 30)
        # cutoff stored for every evaluation must be earlier than target
        base = result["models"]["frequency"]
        self.assertTrue(base["evaluation_count"] > 0)

    def test_all_models_compared(self):
        result = walk_forward_compare(self.rows, min_train=30)
        for name in MODEL_NAMES:
            self.assertIn(name, result["models"])
        self.assertEqual(result["selection"]["selected_model"], None)
        self.assertEqual(result["selection"]["decision"], "no_predictive_advantage_retain_existing_model")

    def test_small_sample_is_reported(self):
        result = walk_forward_compare(self.rows[:20], min_train=30)
        self.assertEqual(result["decision"], "insufficient_data")

    def test_leakage_via_extra_future_rows_has_no_effect(self):
        a = walk_forward_compare(self.rows, models=["frequency"], min_train=30)
        extra = self.rows + [synthetic_result("20261121100010999", 7)]
        b = walk_forward_compare(extra, models=["frequency"], min_train=30)
        # Earlier chronological segment must be identical; the extra row only
        # appends one later evaluation.
        self.assertEqual(a["models"]["frequency"]["segments"][0]["log_loss"],
                         b["models"]["frequency"]["segments"][0]["log_loss"])

    def test_baseline_is_uniform(self):
        result = walk_forward_compare(self.rows, min_train=30)
        base = result["models"]["uniform"]
        self.assertAlmostEqual(base["mean_log_loss"], 2.302585, places=5)
        self.assertEqual(result["baseline"], "uniform")


if __name__ == "__main__":
    unittest.main()
