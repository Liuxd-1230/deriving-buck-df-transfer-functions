import unittest
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.test_chinese_report_output import minimal_artifacts

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts" / "render_derivation_report.py"


class ReportDerivationStepsTests(unittest.TestCase):
    def test_report_contains_layered_derivation_steps(self) -> None:
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
                "--derivation", str(paths["derivation"]),
                "--formula-origin", str(paths["formula_origin"]),
                "--checker-result", str(paths["checker_result"]),
                "--out", str(out),
                "--manifest", str(manifest),
            ], cwd=ROOT, check=True, text=True, capture_output=True, timeout=60)
            text = out.read_text(encoding="utf-8")

        for phrase in [
            "event condition / comparator equation",
            "sampled variable / sensing path",
            "perturbation variable definition",
            "modulator 或 describing-function interface",
            "power-stage interface",
            "loop gain / return ratio / closed-loop mapping",
            "target transfer definition",
            "final candidate expression",
        ]:
            self.assertIn(phrase, text)
        self.assertIn("sampling instant", text)
        self.assertIn("Dirichlet value", text)
        self.assertIn("1-exp(-s*T0)", text)


if __name__ == "__main__":
    unittest.main()
