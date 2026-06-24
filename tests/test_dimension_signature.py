import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from linear_system_transfer import LinearSystemError, solve_linear_system
from tests.test_linear_equation_system_transfer import open_modulator_system


class DimensionSignatureTests(unittest.TestCase):
    def test_slope_like_hs_cannot_be_used_as_duty_to_voltage_transfer(self) -> None:
        system = open_modulator_system()
        for coefficient in system["coefficient_definitions"]:
            if coefficient["symbol"] == "Hs":
                coefficient["unit_signature"] = "V/s"

        with self.assertRaisesRegex(LinearSystemError, "FAIL_DIMENSION_SIGNATURE_MISMATCH"):
            solve_linear_system(system)


if __name__ == "__main__":
    unittest.main()
