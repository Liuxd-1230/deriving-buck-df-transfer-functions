import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MarkdownIsNotEvidenceTests(unittest.TestCase):
    def test_markdown_cannot_replace_proof_object(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "derivation.md"
            report.write_text("# Correct transfer function\nGvc = 1\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "check_proof_object.py"),
                 "--proof", str(report)],
                cwd=ROOT, text=True, capture_output=True, timeout=30,
            )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "FAIL_NOT_PROOF_OBJECT")


if __name__ == "__main__":
    unittest.main()
