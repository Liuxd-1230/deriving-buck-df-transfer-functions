import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts" / "render_derivation_report.py"


class AskUserOnlyReportTests(unittest.TestCase):
    def test_ask_user_only_report_has_no_model_id_or_candidate_transfer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            intake = root / "intake_status.json"
            intake.write_text(json.dumps({
                "intake_version": "0.4",
                "status": "INCOMPLETE",
                "missing": ["sensing_layer", "comparator_inputs"],
                "action": "ASK_USER_ONLY",
                "normalized": {"case_id": "blocked-case", "target_transfer": "Gvc"},
            }, ensure_ascii=False), encoding="utf-8")
            out = root / "report.md"
            manifest = root / "report_manifest.json"

            subprocess.run([
                sys.executable, str(RENDERER),
                "--intake-status", str(intake),
                "--out", str(out),
                "--manifest", str(manifest),
            ], cwd=ROOT, check=True, text=True, capture_output=True, timeout=60)
            text = out.read_text(encoding="utf-8")

        self.assertIn("未完成推导：信息不足", text)
        self.assertIn("sensing_layer", text)
        self.assertNotIn("候选传函", text)
        self.assertNotIn("model_id", text)


if __name__ == "__main__":
    unittest.main()
