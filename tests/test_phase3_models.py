"""Phase 3 model consistency, normalization and leakage tests."""
import math
import unittest

from hmx.engine import EngineConfig
from hmx.models import MODEL_NAMES, build_prediction, derive_outputs, model_probs
from hmx.rules import COLOUR_SETS
from hmx.importer import parse_csv
from tests.common import PHASE0_CSV


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = parse_csv(PHASE0_CSV.read_text(encoding="utf-8"))
        cls.numbers = [int(r["result_number"]) for r in cls.rows]

    def test_all_models_normalized_and_deterministic(self):
        for name in MODEL_NAMES:
            p1 = model_probs(name, self.numbers)
            p2 = model_probs(name, self.numbers)
            self.assertEqual(p1, p2)
            self.assertAlmostEqual(sum(p1.values()), 1.0, places=9)
            self.assertTrue(all(v >= 0 for v in p1.values()))

    def test_derived_outputs_consistent(self):
        for name in MODEL_NAMES:
            p = model_probs(name, self.numbers)
            out = derive_outputs(p)
            self.assertAlmostEqual(out["colour_probs"]["violet"], p[0] + p[5], places=9)
            self.assertAlmostEqual(out["big_prob"], sum(p[i] for i in range(5, 10)), places=9)
            self.assertAlmostEqual(out["big_prob"] + out["small_prob"], 1.0, places=9)
            self.assertEqual(out["selected_size"], "Big" if out["big_prob"] >= out["small_prob"] else "Small")

    def test_insufficient_data(self):
        p = build_prediction(self.rows[:5], model_name="frequency", data_cutoff_period=self.rows[4]["period_id"])
        self.assertEqual(p.status, "insufficient_data")

    def test_future_data_leakage_impossible(self):
        cutoff = self.rows[25]["period_id"]
        a = build_prediction(self.rows, model_name="frequency", data_cutoff_period=cutoff)
        b = build_prediction(self.rows[:26], model_name="frequency", data_cutoff_period=cutoff)
        self.assertEqual(a.number_probs, b.number_probs)
        self.assertEqual(a.dataset_version, b.dataset_version)

    def test_prediction_metadata(self):
        p = build_prediction(self.rows, model_name="bayesian", data_cutoff_period=self.rows[-1]["period_id"])
        cfg = p.model_config
        self.assertEqual(cfg["model_name"], "bayesian")
        self.assertIn("model_version", cfg)
        self.assertIn("model_confidence_top_probability", cfg)
        self.assertIn("model_uncertainty_normalized_entropy", cfg)
        self.assertIn("confidence_note", cfg)
        self.assertIn("data_quality_status", cfg)
        self.assertIn("validation_status", cfg)
        self.assertLess(cfg["model_confidence_top_probability"], 1.0)

    def test_colour_overlap_documented(self):
        self.assertEqual(COLOUR_SETS[0], ("red", "violet"))
        self.assertEqual(COLOUR_SETS[5], ("green", "violet"))


if __name__ == "__main__":
    unittest.main()
