import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReadmeContractTests(unittest.TestCase):
    def test_readme_covers_install_use_and_evidence_boundaries(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        required = (
            "安装",
            "快速开始",
            "cot-cm-li-lee-2010",
            "cot-cm-external-ramp-tian-2015",
            "v2-cot-li-lee-2009",
            "rbcot-esr-lu-2023",
            "preflight_intake.py",
            "--intake-status",
            "proof_object.json",
            "formula_registry.yaml",
            "check_proof_object.py",
            "make-protocol-case",
            "df_protocol_checker.py",
            "PAPER_GROUNDED_PARTIAL",
            "PROTOCOL_DERIVED_UNVERIFIED",
            "Zotero",
            "协议完整性",
            "物理正确性",
            "结构化主路径",
            "报告渲染器",
            "不会自动",
            "ASK_USER_ONLY",
            "DF_REGISTERED_DIRECT",
        )
        for token in required:
            self.assertIn(token, text, token)

    def test_readme_states_unsupported_boundaries(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for token in ("DCM", "multiphase overlap", "pulse skipping", "平均模型"):
            self.assertIn(token, text, token)


if __name__ == "__main__":
    unittest.main()
