import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_rc_memory_factor import check_rc_memory_factor


def rc_case() -> dict:
    tau = 4.8e6 * 2e-12
    ts = 2.02e-6
    return {
        "case_id": "rc-state-valley-cot",
        "target_transfer": "Gvc",
        "control_family": "COT",
        "comparator_input_origin": "switch_node_rc",
        "sensing_layer": {
            "type": "custom_sensing_network",
            "input_variable": "switch_node",
            "output_variable": "comparator_negative",
            "network_type": "RC_lowpass",
            "R": 4.8e6,
            "C": 2e-12,
            "tau": tau,
            "validation": "user_supplied",
        },
        "switching": {"Ts": ts},
        "comparator_ramp_model": {
            "type": "rc_derived_state",
            "R": 4.8e6,
            "C": 2e-12,
            "tau": tau,
            "p": math.exp(-ts / tau),
            "requires_memory_treatment": True,
            "memory_treatment": "discrete_state",
            "Kmod": "D*(1-p*z^-1)/(sf*Tsw)",
            "validation_level": "PROTOCOL_DERIVED_UNVERIFIED",
        },
    }


class RcStateKmodMemoryFactorTests(unittest.TestCase):
    def test_slope_only_kmod_fails_for_rc_derived_ramp(self) -> None:
        artifact = rc_case()
        artifact["comparator_ramp_model"] |= {
            "Kmod": "((1-exp(-s*Ton))/(1-exp(-s*Ts)))*(1/(Ts*abs(Sfall)))",
            "memory_treatment": None,
        }

        result = check_rc_memory_factor(artifact)

        self.assertEqual(result["status"], "FAIL")
        self.assertIn("FAIL_RC_DERIVED_RAMP_SLOPE_ONLY", result["errors"])

    def test_missing_tau_or_memory_factor_fails(self) -> None:
        artifact = rc_case()
        artifact["comparator_ramp_model"].pop("tau")
        artifact["sensing_layer"].pop("tau")

        result = check_rc_memory_factor(artifact)

        self.assertEqual(result["status"], "FAIL")
        self.assertIn("FAIL_MISSING_RC_TAU", result["errors"])

    def test_memory_aware_kmod_is_only_protocol_derived_unverified(self) -> None:
        result = check_rc_memory_factor(rc_case())

        self.assertIn(result["status"], {"PASS", "WARN"})
        self.assertEqual(result["validation_level"], "PROTOCOL_DERIVED_UNVERIFIED")
        self.assertNotIn("PAPER_GROUNDED_PARTIAL", result.get("claims_allowed", []))


if __name__ == "__main__":
    unittest.main()
