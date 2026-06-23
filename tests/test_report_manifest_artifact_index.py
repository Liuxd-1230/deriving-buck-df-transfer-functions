import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_chinese_report_output import minimal_artifacts

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts" / "render_derivation_report.py"


class ReportManifestTests(unittest.TestCase):
    def test_manifest_lists_all_evidence_artifacts_and_report_has_checkout_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = minimal_artifacts(root)
            out = root / "report.md"
            manifest_path = root / "report_manifest.json"
            subprocess.run([
                sys.executable, str(RENDERER),
                "--intake-status", str(paths["intake"]),
                "--classification", str(paths["classification"]),
                "--proof-object", str(paths["proof_object"]),
                "--derivation", str(paths["derivation"]),
                "--formula-origin", str(paths["formula_origin"]),
                "--checker-result", str(paths["checker_result"]),
                "--bode-summary", str(paths["bode_summary"]),
                "--mismatch-report", str(paths["mismatch_report"]),
                "--out", str(out),
                "--manifest", str(manifest_path),
            ], cwd=ROOT, check=True, text=True, capture_output=True, timeout=60)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            report = out.read_text(encoding="utf-8")

        for key in (
            "intake", "classification", "proof_object", "derivation",
            "formula_origin", "checker_result", "bode_summary", "mismatch_report",
        ):
            self.assertIn(key, manifest["artifacts"])
        self.assertIn("用途", report)
        self.assertIn("关键字段", report)
        self.assertIn("人工复查", report)


if __name__ == "__main__":
    unittest.main()
