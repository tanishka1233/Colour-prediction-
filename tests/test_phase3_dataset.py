"""Phase 3.1 dataset profile + metadata export tests."""
import json
import tempfile
import unittest
from pathlib import Path

from hmx.dataset import export_csv_with_metadata, export_json_with_metadata, export_metadata, profile
from hmx.importer import parse_csv, parse_json
from tests.common import PHASE0_CSV


class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = parse_csv(PHASE0_CSV.read_text(encoding="utf-8"))

    def test_profile(self):
        p = profile(self.rows)
        self.assertEqual(p["total_records"], 46)
        self.assertEqual(p["missing_period_count"], 22)
        self.assertEqual(p["duplicate_period_count"], 0)
        self.assertEqual(p["invalid_result_count"], 0)
        self.assertTrue(all(p["mapping_verification"].values()))

    def test_metadata_exports_roundtrip(self):
        meta = export_metadata(self.rows)
        csv_text = export_csv_with_metadata(self.rows, meta)
        self.assertTrue(csv_text.startswith("# dataset_generation_time"))
        self.assertEqual(len(parse_csv(csv_text)), 46)
        json_text = export_json_with_metadata(self.rows, meta)
        obj = json.loads(json_text)
        self.assertEqual(len(obj["records"]), 46)
        self.assertEqual(obj["metadata"]["record_count"], 46)
        self.assertEqual(len(parse_json(json_text)), 46)

    def test_export_metadata_fields(self):
        meta = export_metadata(self.rows)
        for key in ("dataset_generation_time", "record_count", "period_range",
                    "data_source", "validation_summary"):
            self.assertIn(key, meta)


if __name__ == "__main__":
    unittest.main()
