import unittest

from hmx.engine import EngineConfig, predict
from tests.common import PHASE0_CSV, synthetic_series
from hmx.importer import parse_csv


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.rows = parse_csv(PHASE0_CSV.read_text(encoding="utf-8"))

    def test_probabilities_normalized_and_deterministic(self):
        cfg = EngineConfig(min_history=10, analysis_window=100)
        a = predict(self.rows, cfg, data_cutoff_period=self.rows[-1]["period_id"])
        b = predict(self.rows, cfg, data_cutoff_period=self.rows[-1]["period_id"])
        self.assertEqual(a.status, "ok")
        self.assertAlmostEqual(sum(a.number_probs.values()), 1.0, places=9)
        self.assertEqual(a.number_probs, b.number_probs)
        self.assertEqual(a.dataset_version, b.dataset_version)

    def test_future_data_leakage_prevented(self):
        cutoff = self.rows[20]["period_id"]
        a = predict(self.rows, data_cutoff_period=cutoff)
        b = predict(self.rows[:21], data_cutoff_period=cutoff)
        self.assertEqual(a.number_probs, b.number_probs)
        self.assertLessEqual(a.sample_count, 21)

    def test_insufficient_data(self):
        p = predict(self.rows[:3], EngineConfig(min_history=30))
        self.assertEqual(p.status, "insufficient_data")
        self.assertIsNone(p.selected_number)
        self.assertAlmostEqual(sum(p.number_probs.values()), 1.0)

    def test_colour_overlap_and_size(self):
        p = predict(self.rows, EngineConfig(min_history=10))
        self.assertGreater(p.colour_probs["violet"], 0)
        self.assertAlmostEqual(p.big_prob + p.small_prob, 1.0, places=9)
        # violet = P(0)+P(5) and is intentionally not normalized with red/green
        self.assertAlmostEqual(p.colour_probs["violet"],
                               p.number_probs[0] + p.number_probs[5], places=9)

    def test_zero_weights_falls_back_to_uniform(self):
        cfg = EngineConfig(min_history=5, weights={"frequency": 0, "recency": 0,
                                                   "transition": 0, "bayesian": 0})
        p = predict(self.rows[:10], cfg)
        self.assertTrue(all(abs(v - .1) < 1e-9 for v in p.number_probs.values()))

    def test_transition_uses_last_observed_only(self):
        rows = synthetic_series(100, [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 2])
        p = predict(rows, EngineConfig(min_history=5))
        self.assertIn("transition", p.method_probs)
        self.assertAlmostEqual(sum(p.method_probs["transition"].values()), 1.0, places=9)


if __name__ == "__main__":
    unittest.main()
