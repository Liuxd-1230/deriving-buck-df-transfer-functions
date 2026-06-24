import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_rc_memory_factor import check_rc_memory_factor
from run_validation_checks import build_unified_checker_result


def rc_ramp() -> dict:
    return {
        "type": "rc_derived_state",
        "R": 1000,
        "C": 1e-9,
        "tau": 1e-6,
        "Ts": 2e-6,
        "p": 0.1353352832366127,
        "Kmod": "D*(1-p)/(sf*Ts)",
        "memory_treatment": "state_recurrence",
    }


class RcMemoryCheckNotSkippedTests(unittest.TestCase):
    def assert_not_skipped(self, artifact: dict) -> None:
        result = check_rc_memory_factor(artifact)
        self.assertNotEqual(result["status"], "NOT_APPLICABLE")

    def test_top_level_proof_ramp_model_runs_check(self) -> None:
        self.assert_not_skipped({"comparator_ramp_model": rc_ramp()})

    def test_proof_sensing_layer_ramp_model_runs_check(self) -> None:
        self.assert_not_skipped({"sensing_layer": {"comparator_ramp_model": rc_ramp()}})

    def test_intake_normalized_sensing_layer_ramp_model_runs_check(self) -> None:
        self.assert_not_skipped({"intake": {"normalized": {"sensing_layer": {"comparator_ramp_model": rc_ramp()}}}})

    def test_report_exists_cannot_skip_formula_rendering_check(self) -> None:
        result = build_unified_checker_result(report_text="plain report", derivation={})

        self.assertNotEqual(result["checks"]["report_formula_rendering_check"]["status"], "NOT_APPLICABLE")


if __name__ == "__main__":
    unittest.main()
