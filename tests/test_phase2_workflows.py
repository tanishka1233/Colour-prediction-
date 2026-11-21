"""Phase 2: GitHub Actions workflow sanity checks (no PyYAML dependency)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def load(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class WorkflowTests(unittest.TestCase):
    def test_required_workflow_files(self):
        for name in ("ci.yml", "maintenance.yml", "collect-history.yml"):
            self.assertTrue((WORKFLOWS / name).is_file(), f"missing {name}")

    def test_basic_yaml_hygiene(self):
        for path in WORKFLOWS.glob("*.yml"):
            text = load(path)
            self.assertNotIn("\t", text, f"tabs in {path.name}")
            self.assertIn("name:", text)
            self.assertIn("on:", text)
            self.assertIn("jobs:", text)

    def test_ci_workflow(self):
        text = load(WORKFLOWS / "ci.yml")
        for token in ("push:", "pull_request:", "workflow_dispatch:", "actions/checkout",
                      "actions/setup-python", "unittest discover", "compileall"):
            self.assertIn(token, text)

    def test_maintenance_workflow(self):
        text = load(WORKFLOWS / "maintenance.yml")
        self.assertIn("schedule:", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("cron:", text)
        self.assertIn("unittest discover", text)

    def test_collect_history_workflow_is_safe(self):
        text = load(WORKFLOWS / "collect-history.yml")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("schedule:", text)
        self.assertIn("collect-history", text)
        self.assertFalse(re.search(r"git\s+add\s+\S*\.sqlite", text))
        self.assertNotIn("Login", text)
        self.assertNotIn("Bet", text)


if __name__ == "__main__":
    unittest.main()
