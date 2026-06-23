import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_chinese_report_output import minimal_artifacts

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts" / "render_derivation_report.py"


class ReportCheckerResultsVisibleTests(unittest.TestCase):
    def test_checker_table_exposes_status_reason_blocking_and_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = minimal_artifacts(root)
            out = root / "report.md"
            manifest = root / "report_manifest.json"
            subprocess.run([
                sys.executable, str(RENDERER),
                "--intake-status", str(paths["intake"]),
                "--classification", str(paths["classification"]),
                "--proof-object", str(paths["proof_object"]),
                "--formula-origin", str(paths["formula_origin"]),
                "--checker-result", str(paths["checker_result"]),
                "--out", str(out),
                "--manifest", str(manifest),
            ], cwd=ROOT, check=True, text=True, capture_output=True, timeout=60)
            text = out.read_text(encoding="utf-8")

        self.assertIn("| checker | status | reason | blocking | related artifact |", text)
        for checker in (
            "preflight_intake",
            "model_classification",
            "formula_consistency",
            "proof_object_check",
            "normalization_check",
            "power_stage_dynamics_check",
            "validation_policy_check",
            "forbidden_claim_check",
            "mismatch_report_check",
        ):
            self.assertIn(checker, text)


if __name__ == "__main__":
    unittest.main()
