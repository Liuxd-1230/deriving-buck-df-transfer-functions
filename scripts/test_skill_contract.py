#!/usr/bin/env python3
"""Static contract tests for retained paper models under v0.3.1."""

from __future__ import annotations

import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent


class SkillContractTests(unittest.TestCase):
    def test_skill_routes_to_the_paper_formula_library_and_generators(self) -> None:
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("v0.3.1", text)
        self.assertIn("references/df-coefficient-library.md", text)
        self.assertIn("registries/formula_registry.yaml", text)
        self.assertIn("make-case", text)
        for model_id in (
            "cot-cm-li-lee-2010",
            "cot-cm-external-ramp-tian-2015",
            "rbcot-esr-lu-2023",
            "v2-cot-li-lee-2009",
        ):
            self.assertIn(model_id, text)

    def test_formula_library_contains_provenance_and_failure_boundaries(self) -> None:
        text = (SKILL_DIR / "references" / "df-coefficient-library.md").read_text(
            encoding="utf-8"
        )
        for marker in (
            "10.1109/TPEL.2010.2040123",
            "10.1109/TPEL.2015.2508037",
            "10.1109/TPEL.2023.3254906",
            "Li/Lee 2009",
            "derived-adapter",
            "EXCLUDED_NON_DF",
            "多相 overlap",
        ):
            self.assertIn(marker, text)

    def test_validation_report_keeps_unverified_claims_explicit(self) -> None:
        text = (SKILL_DIR / "VALIDATION.md").read_text(encoding="utf-8")
        self.assertIn("EXCLUDED_NON_DF", text)
        self.assertIn("Switching simulation", text)
        self.assertIn("NOT_VERIFIED", text)
        self.assertIn("PARTIALLY_VERIFIED", text)


if __name__ == "__main__":
    unittest.main()
