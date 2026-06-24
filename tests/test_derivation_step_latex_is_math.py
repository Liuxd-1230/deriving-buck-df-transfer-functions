import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_report_markdown_format import ReportFormatError, validate_derivation_steps
from tests.test_report_typora_math_format import v045_derivation


class DerivationStepLatexIsMathTests(unittest.TestCase):
    def test_natural_language_latex_fails(self) -> None:
        derivation = v045_derivation()
        derivation["derivation_steps"][0]["latex"] = "Valley comparison: movable off-edge when Vsense crosses Vref"

        with self.assertRaisesRegex(ReportFormatError, "FAIL_DERIVATION_STEP_LATEX_NOT_MATH"):
            validate_derivation_steps(derivation)


if __name__ == "__main__":
    unittest.main()
