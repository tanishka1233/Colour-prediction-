"""Phase 3 statistical function tests (no third-party scientific packages)."""
import unittest

from hmx.stats import (benjamini_hochberg, binary_segmentation, chi2_sf,
                       chi_square_gof, chi_square_uniform, counter_stats,
                       paired_bootstrap_ci, runs_test, transition_matrix,
                       wilson_interval)


class StatsTests(unittest.TestCase):
    def test_chi2_sf_known_quantiles(self):
        self.assertAlmostEqual(chi2_sf(3.841, 1), 0.05, places=3)
        self.assertAlmostEqual(chi2_sf(16.919, 9), 0.05, places=3)
        self.assertEqual(chi2_sf(0, 9), 1.0)

    def test_chi_square_gof_uses_custom_baseline(self):
        # 40 red-only, 40 green-only, 10+10 violet under uniform-number baseline
        result = chi_square_gof([40, 40, 10, 10], [0.4, 0.4, 0.1, 0.1])
        self.assertAlmostEqual(result["statistic"], 0.0, places=6)
        self.assertGreater(result["p_value"], 0.99)
        wrong = chi_square_uniform([40, 40, 10, 10])
        self.assertLess(wrong["p_value"], 0.001)  # uniform-4 is the wrong baseline

    def test_wilson_interval_contains_point_estimate(self):
        ci = wilson_interval(3, 10)
        self.assertLess(ci["lower"], 0.3)
        self.assertGreater(ci["upper"], 0.3)

    def test_runs_test_small_sample(self):
        result = runs_test([0, 1, 0, 1])
        self.assertIsNone(result["p_value"])

    def test_transition_matrix_shape(self):
        result = transition_matrix([0, 1, 1, 2, 2, 2], 3)
        self.assertEqual(len(result["observed"]), 3)
        self.assertEqual(result["transitions"], 5)
        self.assertIn("min_expected", result)

    def test_benjamini_hochberg(self):
        adjusted = benjamini_hochberg([0.01, 0.02, 0.5])
        self.assertTrue(adjusted[0]["significant"])
        self.assertEqual(adjusted[0]["p_value"], 0.01)
        self.assertGreaterEqual(adjusted[2]["adjusted_p"], adjusted[1]["adjusted_p"])

    def test_paired_bootstrap_is_deterministic(self):
        a = paired_bootstrap_ci([-0.1, 0.0, 0.2, -0.3, 0.1])
        b = paired_bootstrap_ci([-0.1, 0.0, 0.2, -0.3, 0.1])
        self.assertEqual(a, b)
        self.assertLess(a["lower"], a["upper"])

    def test_change_points_exploratory(self):
        series = [0] * 12 + [9] * 12
        points = binary_segmentation(series, min_segment=6)
        self.assertTrue(points)
        self.assertTrue(all("note" in p for p in points))

    def test_counter_stats(self):
        result = counter_stats([0, 0, 1, 2], [0, 1, 2])
        self.assertEqual(result["counts"], [2, 1, 1])
        self.assertEqual(result["sample_size"], 4)


if __name__ == "__main__":
    unittest.main()
