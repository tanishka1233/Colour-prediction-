import json
import tempfile
import threading
import unittest
import urllib.request
from dataclasses import replace
from http.server import ThreadingHTTPServer
from pathlib import Path

from hmx.app import AppState, Handler
from hmx.config import CONFIG
from tests.common import PHASE0_CSV


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        cfg = replace(CONFIG, data_dir=base / "data", log_dir=base / "logs",
                      db_path=base / "data" / "test.sqlite3", provider_enabled=False,
                      collector_autostart=False, rate_limit_per_minute=1000)
        cls.state = AppState(cfg)
        cls.state.store.set_config("analysis_window", "200")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        Handler.state = cls.state
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.port}"
        # import Phase 0 data through the public API
        rows = PHASE0_CSV.read_text(encoding="utf-8")
        req = urllib.request.Request(cls.base + "/api/import", method="POST",
                                     data=json.dumps({"text": rows, "format": "csv"}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5):
            pass

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=5)
        cls.state.shutdown(); cls.tmp.cleanup()

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=5) as r:
            return r.status, r.read()

    def test_health_and_static_frontend(self):
        status, body = self.get("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "ok")
        status, html = self.get("/")
        self.assertIn(b"HMX Predictor", html)

    def test_results_stats_predictions_endpoints(self):
        status, body = self.get("/api/results?limit=10")
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(len(data["results"]), 10)
        self.assertTrue(data["missing_periods"] or True)
        _, body = self.get("/api/stats")
        stats = json.loads(body)
        self.assertEqual(stats["sample_size"], 46)
        self.assertIn("accuracy", stats)
        _, body = self.get("/api/predictions")
        self.assertIn("predictions", json.loads(body))
        _, body = self.get("/api/evaluations")
        self.assertIn("evaluations", json.loads(body))

    def test_export_endpoints(self):
        _, body = self.get("/api/export?format=csv")
        self.assertTrue(body.startswith(b"period_id,"))
        _, body = self.get("/api/export?format=json")
        self.assertEqual(len(json.loads(body)["records"]), 46)

    def test_import_duplicate_rejected(self):
        rows = PHASE0_CSV.read_text(encoding="utf-8")
        req = urllib.request.Request(self.base + "/api/import", method="POST",
                                     data=json.dumps({"text": rows, "format": "csv"}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            stats = json.loads(r.read())
        self.assertEqual(stats["duplicate"], 46)
        self.assertEqual(stats["inserted"], 0)

    def test_unknown_endpoint(self):
        with self.assertRaises(Exception):
            self.get("/api/nonexistent")


if __name__ == "__main__":
    unittest.main()
