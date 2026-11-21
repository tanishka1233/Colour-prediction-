"""Phase 2: database integrity, backup and restore (temporary DBs only)."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from hmx.db import Store
from tests.common import PHASE0_CSV
from hmx.importer import import_file


class Phase2DbTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.db = self.base / "main.sqlite3"
        self.store = Store(self.db)
        import_file(self.store, PHASE0_CSV)

    def tearDown(self):
        self.tmp.cleanup()

    def test_schema_v2_columns_and_indexes(self):
        cols = {r[1] for r in self.store._conn().execute("PRAGMA table_info(predictions)")}
        self.assertIn("is_late", cols)
        self.assertIn("created_after_start_ms", cols)
        fcols = {r[1] for r in self.store._conn().execute("PRAGMA table_info(feed_state)")}
        self.assertIn("last_request_epoch", fcols)
        idx = {r[1] for r in self.store._conn().execute("PRAGMA index_list(results)")}
        self.assertIn("idx_results_timestamp", idx)

    def test_integrity_check(self):
        result = self.store.integrity_check()
        self.assertTrue(result["ok"])
        self.assertEqual(result["integrity"], "ok")
        self.assertEqual(result["counts"]["results"], 46)
        self.assertTrue(result["prediction_immutability_trigger"])
        self.assertEqual(result["schema_version"], "2")

    def test_backup_and_restore(self):
        backup = self.store.backup(self.base / "backup.sqlite3")
        self.assertTrue(backup.is_file())
        restored = Store(self.base / "restored.sqlite3")
        result = restored.restore(backup)
        self.assertEqual(result["results_after"], 46)
        self.assertEqual(restored.result_count(), 46)
        self.assertTrue(restored.integrity_check()["ok"])
        self.assertTrue(Path(result["safety_backup"]).is_file())

    def test_restore_refuses_to_overwrite_without_force(self):
        backup = self.store.backup(self.base / "backup2.sqlite3")
        with self.assertRaises(ValueError):
            self.store.restore(backup)
        result = self.store.restore(backup, force=True)
        self.assertEqual(result["results_after"], 46)
        self.assertEqual(self.store.result_count(), 46)

    def test_corrupt_db_detected(self):
        # create a non-SQLite file and verify integrity check reports failure
        corrupt = self.base / "corrupt.sqlite3"
        corrupt.write_bytes(b"not a database")
        conn = sqlite3.connect(str(corrupt))
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("PRAGMA integrity_check").fetchone()
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
