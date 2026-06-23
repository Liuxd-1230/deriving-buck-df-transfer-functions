import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_forbidden_claims import scan_forbidden_claims


class ForbiddenClaimsScanTests(unittest.TestCase):
    def test_scanner_covers_english_and_chinese_forbidden_claims(self) -> None:
        text = "This is the final transfer function and 图像复现，完全正确。"

        result = scan_forbidden_claims(text, validation_level="PROTOCOL_DERIVED_UNVERIFIED")

        self.assertEqual(result["status"], "FAIL")
        self.assertIn("final transfer function", result["matches"])
        self.assertIn("图像复现", result["matches"])
        self.assertIn("完全正确", result["matches"])


if __name__ == "__main__":
    unittest.main()
