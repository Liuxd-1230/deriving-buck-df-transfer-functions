import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "artifact_workflow.py"


class WorkflowProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODULE.is_file():
            raise AssertionError("artifact_workflow.py is missing")
        spec = importlib.util.spec_from_file_location("artifact_workflow", MODULE)
        cls.workflow = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(cls.workflow)

    def test_hash_linked_state_chain_verifies(self):
        intake = self.workflow.attach_workflow(
            {"intake_version": "0.4", "status": "COMPLETE"},
            state="PREFLIGHT_INTAKE", intent="user-circuit-derivation",
        )
        classification = self.workflow.attach_workflow(
            {"path": "SAMPLED_DATA_REGISTERED"},
            state="MODEL_CLASSIFY", intent="user-circuit-derivation", predecessor=intake,
        )
        proof = self.workflow.attach_workflow(
            {"proof_version": "0.4"},
            state="FORMULA_BINDING", intent="user-circuit-derivation", predecessor=classification,
        )
        self.workflow.verify_workflow(intake, expected_state="PREFLIGHT_INTAKE")
        self.workflow.verify_workflow(classification, expected_state="MODEL_CLASSIFY", predecessor=intake)
        self.workflow.verify_workflow(proof, expected_state="FORMULA_BINDING", predecessor=classification)

    def test_tampered_artifact_hash_is_rejected(self):
        intake = self.workflow.attach_workflow(
            {"status": "COMPLETE"}, state="PREFLIGHT_INTAKE", intent="paper-benchmark",
        )
        artifact = self.workflow.attach_workflow(
            {"path": "SAMPLED_DATA_REGISTERED"},
            state="MODEL_CLASSIFY", intent="paper-benchmark", predecessor=intake,
        )
        artifact["path"] = "DF_REGISTERED_DIRECT"
        with self.assertRaisesRegex(self.workflow.WorkflowError, "hash"):
            self.workflow.verify_workflow(artifact)

    def test_skipped_predecessor_state_is_rejected(self):
        intake = self.workflow.attach_workflow(
            {"status": "COMPLETE"}, state="PREFLIGHT_INTAKE", intent="demo",
        )
        with self.assertRaisesRegex(self.workflow.WorkflowError, "transition"):
            self.workflow.attach_workflow(
                {"proof_version": "0.4"}, state="FORMULA_BINDING", intent="demo", predecessor=intake,
            )


if __name__ == "__main__":
    unittest.main()
