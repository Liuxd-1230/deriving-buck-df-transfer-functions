import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from physics_workflow import PhysicsWorkflowError, STATE_PREDECESSOR, attach_physics_workflow, verify_physics_workflow


class V05WorkflowTests(unittest.TestCase):
    def test_exact_full_state_prefix_is_hash_linked(self):
        artifact = None
        for state in STATE_PREDECESSOR:
            artifact = attach_physics_workflow({"payload": state}, state=state, predecessor=artifact)
            verify_physics_workflow(artifact, expected_state=state)
        self.assertEqual(artifact["workflow"]["version"], "0.5")
        self.assertEqual(artifact["workflow"]["history"], list(STATE_PREDECESSOR))

    def test_skipped_state_is_rejected(self):
        intake = attach_physics_workflow({"payload": 1}, state="IMAGE_INTAKE")
        with self.assertRaises(PhysicsWorkflowError):
            attach_physics_workflow({"payload": 2}, state="TOPOLOGY_CONFIRMED", predecessor=intake)

    def test_tampered_payload_is_rejected(self):
        artifact = attach_physics_workflow({"payload": 1}, state="IMAGE_INTAKE")
        artifact["payload"] = 2
        with self.assertRaisesRegex(PhysicsWorkflowError, "hash"):
            verify_physics_workflow(artifact)

    def test_forged_history_is_rejected_even_with_recomputed_self_hash(self):
        from physics_workflow import canonical_hash

        artifact = attach_physics_workflow({"payload": 1}, state="IMAGE_INTAKE")
        artifact["workflow"]["history"] = ["REPORT"]
        artifact["workflow"]["artifact_sha256"] = canonical_hash(artifact)
        with self.assertRaisesRegex(PhysicsWorkflowError, "history"):
            verify_physics_workflow(artifact)


if __name__ == "__main__":
    unittest.main()
