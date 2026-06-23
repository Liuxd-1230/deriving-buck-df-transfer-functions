import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "preflight_intake.py"


class PreflightQuestionTests(unittest.TestCase):
    def run_preflight(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )

    def test_incomplete_text_writes_ask_user_only_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "intake_status.json"
            result = self.run_preflight(
                "--text", str(ROOT / "tests" / "fixtures" / "forward_valley_vcot.txt"),
                "--out", str(output),
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertTrue(output.is_file(), result.stderr)
            status = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(status["status"], "INCOMPLETE")
        self.assertEqual(status["action"], "ASK_USER_ONLY")
        self.assertEqual(status["normalized"]["control_family"], "V-COT")
        self.assertIn("target_transfer", status["missing"])
        self.assertIn("sampling_or_switching_event", status["missing"])
        self.assertIn("comparator_inputs", status["missing"])
        self.assertIn("parameters", status["missing"])

    def test_complete_registered_json_passes_without_sympy(self):
        intake = {
            "intent": "user-circuit-derivation",
            "model_id": "v2-cot-li-lee-2009",
            "target": "Gvc",
            "topology": "buck",
            "conduction_mode": "CCM",
            "phases": 1,
            "control_family": "V-COT",
            "switching_events": [{"name": "valley", "equation": "F_event=vfb-vc=0"}],
            "comparator_inputs": {"positive": "vfb", "negative": "vc"},
            "parameters": {
                "Vin": 12, "Vo": 1.2, "fs": 300000, "L": 3e-7,
                "C": 560e-6, "R": 0.1, "rC": 0.006,
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "intake.json"
            output = Path(directory) / "intake_status.json"
            source.write_text(json.dumps(intake), encoding="utf-8")
            result = self.run_preflight("--intake", str(source), "--out", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            status = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(status["status"], "COMPLETE")
        self.assertEqual(status["action"], "CONTINUE_TO_CLASSIFICATION")
        self.assertEqual(status["missing"], [])

    def test_text_intake_preserves_multiple_targets_and_requires_tloop_loop_break(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = root / "request.txt"
            output = root / "intake_status.json"
            request.write_text("请推导 buck CCM 电路的 Gvc 和 Tloop", encoding="utf-8")
            result = self.run_preflight("--text", str(request), "--out", str(output))
            self.assertEqual(result.returncode, 2, result.stderr)
            status = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(status["status"], "INCOMPLETE_TLOOP_INTAKE")
        self.assertEqual(status["normalized"]["target_transfer"], ["Gvc", "Tloop"])
        self.assertIn("loop_break", status["missing"])
        self.assertEqual(status["action"], "ASK_USER_ONLY")


if __name__ == "__main__":
    unittest.main()
