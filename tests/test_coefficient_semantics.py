import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from linear_system_transfer import LinearSystemError, solve_linear_system
from tests.test_linear_equation_system_transfer import open_modulator_system


class CoefficientSemanticsTests(unittest.TestCase):
    def test_coefficient_from_to_must_match_block_use(self) -> None:
        system = open_modulator_system()
        system["blocks"][0]["from"] = "vc_hat"

        with self.assertRaisesRegex(LinearSystemError, "FAIL_COEFFICIENT_SEMANTICS_CONTRADICT_BLOCK_USE"):
            solve_linear_system(system)


if __name__ == "__main__":
    unittest.main()
