"""Phase 2: CLI commands work end-to-end against temporary databases."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PHASE0 = ROOT / "investigation" / "data" / "wingo_1m_history.csv"


class Phase2CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.env = dict(os.environ)
        self.env.update({"HMX_DB_PATH": str(self.base / "cli.sqlite3"),
                         "HMX_DATA_DIR": str(self.base),
                         "HMX_LOG_DIR": str(self.base / "logs"),
                         "HMX_PROVIDER_ENABLED": "0"})

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "hmx.cli", *args], cwd=ROOT,
                              env=self.env, capture_output=True, text=True, timeout=90)

    def test_migrate_import_dbcheck_backup_restore_stats(self):
        self.assertEqual(self.run_cli("migrate").returncode, 0)
        self.assertEqual(self.run_cli("import", str(PHASE0)).returncode, 0)
        check = self.run_cli("db-check")
        self.assertEqual(check.returncode, 0)
        self.assertTrue(json.loads(check.stdout)["ok"])
        backup = self.run_cli("backup")
        self.assertEqual(backup.returncode, 0)
        path = json.loads(backup.stdout)["backup"]
        self.assertTrue(Path(path).is_file())
        fresh_env = dict(self.env, HMX_DB_PATH=str(self.base / "restored.sqlite3"))
        done = subprocess.run([sys.executable, "-m", "hmx.cli", "restore", path],
                              cwd=ROOT, env=fresh_env, capture_output=True, text=True, timeout=90)
        self.assertEqual(done.returncode, 0, done.stderr)
        stats = self.run_cli("stats")
        self.assertEqual(stats.returncode, 0, stats.stderr)
        report = json.loads(stats.stdout)
        self.assertEqual(report["total_predictions"], 0)
        self.assertIn("disclaimer", report)

    def test_collect_history_from_file(self):
        self.run_cli("migrate")
        result = self.run_cli("collect-history", "--file", str(PHASE0))
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["inserted"], 46)
        self.assertIn("limitation", summary)


if __name__ == "__main__":
    unittest.main()
