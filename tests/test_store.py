import sqlite3
import unittest

from tests.common import synthetic_result, temp_store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.store, self.tmp = temp_store()

    def tearDown(self):
        self.tmp.cleanup()

    def test_insert_duplicate_conflict(self):
        row = synthetic_result("20261121100010300", 4)
        self.assertEqual(self.store.insert_result(row), "inserted")
        self.assertEqual(self.store.insert_result(row), "duplicate")
        changed = dict(row, result_number=5, result_colour="green,violet", result_size="Big")
        self.assertEqual(self.store.insert_result(changed), "conflict")
        self.assertEqual(self.store.get_result(row["period_id"])["result_number"], 4)

    def test_unique_period_and_ordering(self):
        for seq, n in [(302, 1), (301, 2), (300, 3)]:
            self.store.insert_result(synthetic_result(f"20261121100010{seq:03d}", n))
        self.assertEqual([r["period_id"] for r in self.store.all_results()],
                         ["20261121100010300", "20261121100010301", "20261121100010302"])

    def test_prediction_immutability(self):
        record = {
            "prediction_id": "p1", "period_id": "20261121100010400",
            "created_at": "2026-11-21T05:00:00Z", "data_cutoff_period": "20261121100010399",
            "dataset_version": "v1", "algorithm_version": "a1",
            "number_probs": {i: 0.1 for i in range(10)}, "colour_probs": {"red": .5, "green": .5, "violet": .2},
            "big_prob": .5, "small_prob": .5, "selected_number": 3, "selected_colour": "green",
            "selected_size": "Small", "sample_count": 46, "model_config": {},
            "prediction_status": "draft",
        }
        self.assertEqual(self.store.insert_prediction(record), "inserted")
        self.assertEqual(self.store.insert_prediction(record), "duplicate")
        self.assertTrue(self.store.publish_prediction(record["period_id"]))
        self.assertFalse(self.store.publish_prediction(record["period_id"]))
        with self.assertRaises(sqlite3.IntegrityError):
            with self.store.transaction() as conn:
                conn.execute("UPDATE predictions SET selected_number=9 WHERE period_id=?", (record["period_id"],))

    def test_feed_state_and_config(self):
        self.store.set_feed_state("history", etag="E1", last_status="ok")
        self.assertEqual(self.store.get_feed_state("history")["etag"], "E1")
        self.store.set_config("analysis_window", "120")
        self.assertEqual(self.store.get_config("analysis_window"), "120")


if __name__ == "__main__":
    unittest.main()
