import unittest

from hmx.rules import (
    ValidationError, colour_for, missing_periods, normalize_colour, size_for, validate_result,
)


class RulesTests(unittest.TestCase):
    def test_number_mapping(self):
        expected = {
            0: "red,violet", 1: "green", 2: "red", 3: "green", 4: "red",
            5: "green,violet", 6: "red", 7: "green", 8: "red", 9: "green",
        }
        for n, colour in expected.items():
            self.assertEqual(colour_for(n), colour)
            self.assertEqual(size_for(n), "Big" if n > 4 else "Small")

    def test_normalize_colour_order(self):
        self.assertEqual(normalize_colour("violet, red"), "red,violet")
        self.assertEqual(normalize_colour("GREEN"), "green")
        with self.assertRaises(ValidationError):
            normalize_colour("blue")

    def test_validate_result_rejects_corruption(self):
        base = {"period_id": "20261121100010300", "result_number": 4,
                "result_colour": "red", "result_size": "Small",
                "result_timestamp": "2026-11-21T05:00:00Z"}
        self.assertEqual(validate_result(base)["result_number"], 4)
        with self.assertRaises(ValidationError):
            validate_result({**base, "result_number": 10})
        with self.assertRaises(ValidationError):
            validate_result({**base, "result_colour": "green"})
        with self.assertRaises(ValidationError):
            validate_result({**base, "period_id": "123"})

    def test_missing_periods(self):
        ids = ["20261121100010300", "20261121100010301", "20261121100010305"]
        gaps = missing_periods(ids)
        self.assertEqual(gaps[0][2], 3)
        self.assertEqual(gaps[0][0], "20261121100010301")


if __name__ == "__main__":
    unittest.main()
