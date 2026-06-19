import json
import subprocess
import sys
import unittest
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check_proof_object.py"
FIXTURES = ROOT / "tests" / "fixtures"


class DirectModelContractTests(unittest.TestCase):
    def check(self, fixture):
        return subprocess.run(
            [sys.executable, str(CHECKER), "--proof", str(FIXTURES / fixture)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=60,
        )

    def test_direct_model_rejects_fake_a_star(self):
        result = self.check("direct_with_fake_a_star.json")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "FAIL_DIRECT_MODEL_FAKE_A_STAR")

    def test_valid_direct_model_passes(self):
        result = self.check("valid_li_lee_2009_direct.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "PASS")

    def test_direct_report_does_not_render_a_star_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.md"
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "df_buck_sympy.py"), "derive",
                 "--proof-object", str(FIXTURES / "valid_li_lee_2009_direct.json"),
                 "--out", str(report)],
                cwd=ROOT, text=True, capture_output=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            text = report.read_text(encoding="utf-8")
        self.assertNotIn("Mapping to a_c/a_g/a_o/a_i", text)
        self.assertIn("direct-transfer", text)


if __name__ == "__main__":
    unittest.main()
