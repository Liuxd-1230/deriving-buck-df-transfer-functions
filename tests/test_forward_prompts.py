import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "scripts" / "preflight_intake.py"


class ForwardPromptTests(unittest.TestCase):
    def test_valley_voltage_cot_stops_before_derivation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status_path = root / "intake_status.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-S",
                    str(PREFLIGHT),
                    "--text",
                    str(ROOT / "tests" / "fixtures" / "forward_valley_vcot.txt"),
                    "--out",
                    str(status_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=30,
            )
            self.assertTrue(status_path.is_file(), result.stderr)
            status = json.loads(status_path.read_text(encoding="utf-8"))

            self.assertEqual(result.returncode, 2)
            self.assertEqual(status["action"], "ASK_USER_ONLY")
            self.assertNotIn("transfer_function", status)
            self.assertNotIn("proof_object", status)
            self.assertEqual(list(root.glob("*.png")), [])


if __name__ == "__main__":
    unittest.main()
