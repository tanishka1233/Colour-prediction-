import unittest

from hmx.importer import export_csv, export_json, import_file, parse_csv, parse_json
from hmx.rules import missing_periods
from tests.common import PHASE0_CSV, temp_store


class ImportExportTests(unittest.TestCase):
    def setUp(self):
        self.store, self.tmp = temp_store()

    def tearDown(self):
        self.tmp.cleanup()

    def test_phase0_csv_import_is_idempotent(self):
        first = import_file(self.store, PHASE0_CSV)
        second = import_file(self.store, PHASE0_CSV)
        self.assertEqual(first["inserted"], 46)
        self.assertEqual(first["invalid"], 0)
        self.assertEqual(second["duplicate"], first["inserted"])
        self.assertEqual(self.store.result_count(), 46)

    def test_csv_json_roundtrip(self):
        import_file(self.store, PHASE0_CSV)
        rows = self.store.all_results()
        csv_text = export_csv(rows)
        json_text = export_json(rows)
        self.assertEqual(len(parse_csv(csv_text)), 46)
        self.assertEqual(len(parse_json(json_text)), 46)
        self.assertIn("red,violet", csv_text)

    def test_invalid_rows_rejected(self):
        stats = import_file(self.store, PHASE0_CSV)
        self.assertEqual(stats["invalid"], 0)
        self.assertEqual(len(missing_periods(r["period_id"] for r in self.store.all_results())), 1)


if __name__ == "__main__":
    unittest.main()
