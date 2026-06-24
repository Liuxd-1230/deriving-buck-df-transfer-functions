import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from linear_system_transfer import LinearSystemError, solve_linear_system
from tests.test_linear_equation_system_transfer import open_modulator_system


class ActiveCoefficientNotDiagnosticTests(unittest.TestCase):
    def test_active_coefficient_defined_only_in_diagnostic_equation_fails(self) -> None:
        system = open_modulator_system()
        system["coefficient_definitions"] = [
            item for item in system["coefficient_definitions"] if item["symbol"] != "K0"
        ]
        system["diagnostic_equations"] = [
            {"id": "diag_ke", "lhs": "K0", "rhs": "D*(1-p*exp(-s*Ts))/(sf*Ts)"}
        ]

        with self.assertRaisesRegex(LinearSystemError, "FAIL_ACTIVE_COEFFICIENT_DEFINED_ONLY_AS_DIAGNOSTIC"):
            solve_linear_system(system)


if __name__ == "__main__":
    unittest.main()
