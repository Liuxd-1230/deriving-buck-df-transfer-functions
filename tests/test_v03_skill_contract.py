import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class V03SkillContractTests(unittest.TestCase):
    def test_skill_enforces_event_first_and_unverified_new_models(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for token in ("F(x,u,t)=0", "UNVERIFIED_NEW_DF_MODEL", "circuit-intake-protocol.md",
                      "df-reasoning-protocol.md", "df_protocol_checker.py"):
            self.assertIn(token, text)

    def test_core_references_exist_and_name_required_contracts(self):
        expected = {
            "circuit-intake-protocol.md": ["5-question quick intake", "AI internal intake checklist"],
            "model-classification.md": ["KNOWN_MODEL", "NEAR_MODEL", "NEW_MODEL", "UNSUPPORTED"],
            "df-reasoning-protocol.md": ["delta_t", "d_hat", "12-step"],
            "protocol-case-schema.md": ["case_version", "df_relation", "validation_status"],
            "validation-status.md": ["PAPER_GROUNDED_VERIFIED", "PROTOCOL_DERIVED_UNVERIFIED"],
            "unsupported-cases.md": ["average model", "multiphase overlap", "pulse skipping"],
        }
        for name, tokens in expected.items():
            text = (ROOT / "references" / name).read_text(encoding="utf-8")
            for token in tokens:
                self.assertIn(token, text, f"{token} missing from {name}")

    def test_each_paper_skeleton_contains_twelve_fields(self):
        names = ["common-edge-sensitivity.md", "li-lee-2010-cot-current-mode.md",
                 "tian-2015-external-ramp.md", "li-lee-2009-v2-cot.md",
                 "lu-2023-rbcot-loopgain.md"]
        fields = ["Paper scope", "Circuit/control law", "Switching event",
                  "Perturbation variables", "Edge sensitivity step", "How DF is formed",
                  "How power stage is coupled", "Final transfer relation", "Approximation made",
                  "Validation used in paper", "What can be generalized", "What must not be generalized"]
        for name in names:
            text = (ROOT / "references" / "paper-proof-skeletons" / name).read_text(encoding="utf-8")
            for field in fields:
                self.assertIn(field, text, f"{field} missing from {name}")

    def test_examples_cover_four_forward_scenarios(self):
        for name in ("intake_known_tian.json", "intake_missing_event.json",
                     "intake_new_rc_ramp_cot.json", "intake_unsupported_overlap.json",
                     "protocol_derivation_template.md"):
            self.assertTrue((ROOT / "examples" / name).is_file(), name)

    def test_validation_keeps_v03_claims_honest(self):
        text = (ROOT / "VALIDATION.md").read_text(encoding="utf-8")
        for token in ("v0.3", "PROTOCOL CHECKER", "SWITCHING SIMULATION",
                      "NOT_VERIFIED", "INDEPENDENT AGENT FORWARD-TEST"):
            self.assertIn(token, text.upper() if token != "v0.3" else text)


if __name__ == "__main__":
    unittest.main()
