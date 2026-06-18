import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from df_protocol_checker import check_protocol_case, check_report_text


FIXTURES = ROOT / "tests" / "protocol_failures"


class ProtocolCheckerTests(unittest.TestCase):
    def fixture(self, name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def test_missing_event(self):
        self.assertEqual(check_protocol_case(self.fixture("missing_event.json"))["status"],
                         "FAIL_MISSING_EVENT")

    def test_missing_edge_perturbation(self):
        self.assertEqual(check_protocol_case(self.fixture("missing_edge_perturbation.json"))["status"],
                         "FAIL_MISSING_EDGE_PERTURBATION")

    def test_multiphase_overlap(self):
        self.assertEqual(check_protocol_case(self.fixture("multiphase_overlap.json"))["status"],
                         "FAIL_UNSUPPORTED_TOPOLOGY")

    def test_average_model_as_df(self):
        self.assertEqual(check_protocol_case(self.fixture("average_model_as_df.json"))["status"],
                         "FAIL_FALSE_DF")

    def test_coefficients_without_source(self):
        self.assertEqual(check_protocol_case(self.fixture("coefficients_without_source.json"))["status"],
                         "FAIL_MISSING_DF_SOURCE")

    def test_bode_only_is_warning(self):
        result = check_protocol_case(self.fixture("bode_only.json"))
        self.assertEqual(result["status"], "WARNING_INCOMPLETE_VALIDATION")
        self.assertTrue(any("switch-state" in warning for warning in result["warnings"]))

    def test_false_verified_claim(self):
        case = self.fixture("bode_only.json")
        case["validation_status"]["level"] = "PAPER_GROUNDED_VERIFIED"
        case["validation_status"]["claim"] = "verified and correct"
        self.assertEqual(check_protocol_case(case)["status"], "FAIL_FALSE_VERIFICATION_CLAIM")

    def test_complete_protocol_case_passes_unverified(self):
        case = self.fixture("bode_only.json")
        case.update({
            "state_variables": ["iL", "vo"],
            "switching_state_equations": {"on": "...", "off": "..."},
            "steady_state_trajectory": "periodic CCM trajectory",
            "perturbation_paths": {"uc_hat": "event"},
            "buck_power_stage_coupling": "CCM Buck equations",
            "transfer_function": "candidate Gvc(s)",
            "sanity_checks": ["symbolic", "dc-limit"],
        })
        case["validation_status"]["completed"] = ["symbolic", "dc-limit", "paper-benchmark", "switching-simulation"]
        case["validation_status"]["missing"] = []
        self.assertEqual(check_protocol_case(case)["status"], "PASS_PROTOCOL_UNVERIFIED")

    def test_markdown_without_required_event_fails(self):
        result = check_report_text("## Model classification\nNEW_MODEL\n## Validation status\nPROTOCOL_DERIVED_UNVERIFIED")
        self.assertEqual(result["status"], "FAIL_MISSING_EVENT")

    def test_markdown_does_not_treat_arbitrary_f_variable_as_event(self):
        text = """## Model classification
NEW_MODEL
F_gain = 0.40
D = 0.4
## Validation status
PROTOCOL_DERIVED_UNVERIFIED
"""
        result = check_report_text(text)
        self.assertEqual(result["status"], "FAIL_MISSING_EVENT")
        self.assertFalse(result["checks"]["event_equation"])

    def test_markdown_recognizes_explicit_edge_event_ending_in_zero(self):
        text = """## Model classification
NEW_MODEL
Switching event: F_off = Ri*iL + vramp - vc = 0
movable edge; Ton fixed
delta_t = -delta_F/Fdot_0
## Describing-function relation
d_hat is an equivalent switching perturbation
## What is paper-derived vs newly derived
paper-inspired-new-derivation
## Validation status
PROTOCOL_DERIVED_UNVERIFIED
missing: switching-simulation
"""
        result = check_report_text(text)
        self.assertTrue(result["checks"]["event_equation"])


if __name__ == "__main__":
    unittest.main()
