import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_chinese_report_output import minimal_artifacts

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts" / "render_derivation_report.py"


class ReportFormulaSourceTests(unittest.TestCase):
    def test_report_contains_formula_source_table_and_coverage(self) -> None:
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

        self.assertIn("| 对象 | 公式 ID | 来源模型 | canonical expression | origin | validation |", text)
        for obj in ("a_c", "Gid", "Ti", "Tc", "sideband"):
            self.assertIn(f"| {obj} |", text)
        self.assertIn("formula_registry.yaml", text)


if __name__ == "__main__":
    unittest.main()
