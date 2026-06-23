import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class V042FormulaAuditDocsTests(unittest.TestCase):
    def test_methodology_documents_practice_first_evidence_levels(self) -> None:
        text = (ROOT / "references" / "paper-bode-validation-spec.md").read_text(encoding="utf-8")
        for phrase in (
            "practice is the final arbiter",
            "实事求是",
            "SUBFORMULA_VERIFIED",
            "CHAIN_VERIFIED",
            "FIGURE_REPRODUCED",
            "SIMULATION_OR_MEASUREMENT_REPRODUCED",
        ):
            self.assertIn(phrase, text)
        self.assertIn("single Bode point is not enough", text)

    def test_model_ontology_keeps_control_method_and_source_index_separate(self) -> None:
        text = (ROOT / "references" / "model-ontology.md").read_text(encoding="utf-8")
        self.assertIn("control ontology", text)
        self.assertIn("source index", text)
        self.assertIn("V-COT sampled-data", text)
        self.assertIn("V2 COT direct-transfer", text)
        self.assertIn("RBCOT loop gain", text)

    def test_li_lee_2010_doc_marks_complete_gvc_as_pending_not_reproduced(self) -> None:
        text = (ROOT / "references" / "li-lee-2010-current-mode-gvc.md").read_text(encoding="utf-8")
        self.assertIn("Eq. (9)", text)
        self.assertIn("Eq. (16)", text)
        self.assertIn("current implementation", text)
        self.assertIn("does not yet claim FIGURE_REPRODUCED", text)
        self.assertIn("Ri sweep", text)
        self.assertIn("external ramp sweep", text)

    def test_skill_routes_formula_audit_to_new_references(self) -> None:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for name in (
            "model-ontology.md",
            "formula-audit-plan.md",
            "df-vs-sampled-method-selection.md",
            "paper-bode-validation-spec.md",
            "li-lee-2010-current-mode-gvc.md",
        ):
            self.assertIn(name, text)


if __name__ == "__main__":
    unittest.main()
