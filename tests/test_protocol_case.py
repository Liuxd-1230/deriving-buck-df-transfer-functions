import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from df_protocol_case import ProtocolCaseError, build_protocol_case, render_protocol_report


def complete_new_intake():
    return {
        "topology": "buck", "conduction_mode": "CCM", "phases": 1,
        "control_family": "custom-cot", "target": "Gvc",
        "control_timing": {"fixed": "Ton", "variable": "Toff/Tsw"},
        "switching_events": [{
            "name": "off_edge", "fixed_or_movable": "movable",
            "equation": "F_off=Ri*iL(t_off)+vramp(t_off)-vc=0",
            "edge_slope": "Fdot_0=dF_off/dt at t_off",
            "delta_edge": "delta_t_off=-delta_F/Fdot_0",
        }],
        "comparator_inputs": {"positive": "vc", "negative": "Ri*iL+vramp"},
        "parameters": {"Vin": 12, "Vo": 1.2, "fs": 300000, "L": 3e-7,
                       "C": 470e-6, "R": 0.1, "rC": 0.001},
        "state_variables": ["iL", "vo"],
        "switching_state_equations": {"on": "L*diL/dt=vg-vo", "off": "L*diL/dt=-vo"},
        "steady_state_trajectory": "piecewise CCM trajectory over one switching period",
        "perturbation_paths": {"uc_hat": "enters F_off", "iL_hat": "enters F_off"},
        "df_relation": {
            "form": "d_hat=a_c*uc_hat+a_g*vg_hat+a_o*vo_hat+a_i*iL_hat",
            "a_c": "A_c(s)", "a_g": "0", "a_o": "0", "a_i": "A_i(s)",
            "origin": "paper-inspired-new-derivation",
            "duty_caveat": "d_hat is an equivalent switching-function perturbation",
        },
        "sanity_checks": ["symbolic", "dc-limit"],
    }


class ProtocolCaseTests(unittest.TestCase):
    def test_new_case_is_unverified_and_preserves_event_chain(self):
        case = build_protocol_case(complete_new_intake())
        self.assertEqual(case["case_version"], "0.3")
        self.assertEqual(case["mode"], "derive-by-protocol")
        self.assertEqual(case["validation_status"]["level"], "PROTOCOL_DERIVED_UNVERIFIED")
        self.assertEqual(case["validation_status"]["claim"], "UNVERIFIED_NEW_DF_MODEL")
        self.assertIn("delta_F", case["switching_events"][0]["delta_edge"])

    def test_missing_event_refuses_case(self):
        intake = complete_new_intake()
        del intake["switching_events"]
        with self.assertRaisesRegex(ProtocolCaseError, "switching_events"):
            build_protocol_case(intake)

    def test_missing_switch_state_model_refuses_case(self):
        intake = complete_new_intake()
        del intake["switching_state_equations"]
        with self.assertRaisesRegex(ProtocolCaseError, "switching_state_equations"):
            build_protocol_case(intake)

    def test_user_coefficients_require_source_event_and_frequency(self):
        intake = complete_new_intake()
        intake["mode"] = "custom-unverified-df"
        intake["df_relation"]["origin"] = "user-supplied"
        with self.assertRaisesRegex(ProtocolCaseError, "df_source"):
            build_protocol_case(intake)

    def test_report_contains_all_protocol_sections(self):
        report = render_protocol_report(build_protocol_case(complete_new_intake()))
        required = ["## Model classification", "## Switching event equation",
                    "## Edge perturbation", "## Describing-function relation",
                    "## Buck power-stage coupling", "## Validation status",
                    "## What is paper-derived vs newly derived"]
        for heading in required:
            self.assertIn(heading, report)
        self.assertIn("Fixed timing: Ton", report)


if __name__ == "__main__":
    unittest.main()
