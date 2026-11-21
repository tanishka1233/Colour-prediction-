import math
import unittest

from hmx.evaluation import UNIFORM_BRIER, UNIFORM_LOG_LOSS, evaluate, summarize, walk_forward
from tests.common import PHASE0_CSV
from hmx.importer import parse_csv


def prediction(actual: int, chosen: int = 3):
    probs = {i: 0.05 for i in range(10)}
    probs[chosen] = 0.55
    probs[9] = 1.0 - sum(probs.values())
    return {"prediction_id": "p", "period_id": "x", "number_probs": probs,
            "colour_probs": {"red": .6, "green": .5, "violet": .1},
            "selected_number": chosen, "selected_colour": "green", "selected_size": "Small"}


class EvaluationTests(unittest.TestCase):
    def test_metrics(self):
        ev = evaluate(prediction(3), 3)
        self.assertEqual(ev["exact_number_hit"], 1)
        self.assertEqual(ev["size_hit"], 1)
        self.assertAlmostEqual(ev["log_loss"], -math.log(0.55))
        self.assertLess(ev["brier_score"], UNIFORM_BRIER)
        self.assertAlmostEqual(ev["baseline_log_loss"], UNIFORM_LOG_LOSS)

    def test_missed_prediction(self):
        ev = evaluate(prediction(3), 8)
        self.assertEqual(ev["exact_number_hit"], 0)
        self.assertEqual(ev["size_hit"], 0)
        self.assertEqual(ev["colour_hit"], 0)

    def test_walk_forward_never_uses_future(self):
        rows = parse_csv(PHASE0_CSV.read_text(encoding="utf-8"))
        evs = walk_forward(rows, min_train=30)
        self.assertTrue(evs)
        self.assertTrue(all(e["exploratory"] for e in evs))
        self.assertEqual(len(evs), len(rows) - 30)
        summary = summarize(evs)
        self.assertEqual(summary["count"], len(evs))
        self.assertEqual(summary["baseline_log_loss"], UNIFORM_LOG_LOSS)

    def test_empty_summary(self):
        self.assertIsNone(summarize([])["exact_accuracy"])


if __name__ == "__main__":
    unittest.main()
