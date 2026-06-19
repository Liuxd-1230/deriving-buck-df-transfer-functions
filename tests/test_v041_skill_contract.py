import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class V041SkillContractTests(unittest.TestCase):
    def test_skill_declares_complete_hash_linked_essf_state_machine(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for state in (
            "INTENT_CLASSIFY", "PREFLIGHT_INTAKE", "MODEL_CLASSIFY",
            "FORMULA_BINDING", "DERIVATION", "CHECKERS", "REPORT",
        ):
            self.assertIn(state, text)
        self.assertIn("derive_transfer.py", text)
        self.assertIn("check_derivation.py", text)
        self.assertIn("render_derivation_report.py", text)

    def test_sampled_data_reasoning_references_exist(self):
        names = (
            "sampled-data-protocol.md", "yan-2022-part-i-proof-skeleton.md",
            "yan-2022-part-ii-proof-skeleton.md", "dirichlet-fm.md",
            "pulse-sideband.md", "power-stage-coupling.md",
            "approximation-policy.md",
        )
        for name in names:
            path = ROOT / "references" / "sampled-data" / name
            self.assertTrue(path.is_file(), name)
            text = path.read_text(encoding="utf-8")
            self.assertIn("formula_id", text, name)
            self.assertIn("失效", text, name)

    def test_docs_do_not_claim_pm_gm_for_non_return_ratios(self):
        combined = "\n".join(
            (ROOT / name).read_text(encoding="utf-8")
            for name in ("README.md", "VALIDATION.md")
        )
        self.assertIn("NOT_APPLICABLE_NON_RETURN_RATIO", combined)
        self.assertIn("Ti/Tv/Tloop", combined)


if __name__ == "__main__":
    unittest.main()
