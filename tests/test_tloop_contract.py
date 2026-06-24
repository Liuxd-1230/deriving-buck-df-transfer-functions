import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from linear_system_transfer import LinearSystemError, solve_linear_system
from tests.test_linear_equation_system_transfer import closed_equivalent_system


class TloopContractV045Tests(unittest.TestCase):
    def test_tloop_requires_loop_break_contract(self) -> None:
        system = closed_equivalent_system()
        system["target"] = {
            "name": "Tloop",
            "output": "vo_hat",
            "input": "vc_hat",
            "response_kind": "return_ratio",
        }

        with self.assertRaisesRegex(LinearSystemError, "FAIL_TLOOP_REQUIRES_LOOP_BREAK"):
            solve_linear_system(system)

    def test_gvc_mislabeled_as_return_ratio_fails(self) -> None:
        system = closed_equivalent_system()
        system["target"]["response_kind"] = "return_ratio"

        with self.assertRaisesRegex(LinearSystemError, "FAIL_GVC_MISLABELED_AS_TLOOP"):
            solve_linear_system(system)


if __name__ == "__main__":
    unittest.main()
