import copy
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from circuit_ir import DIMENSIONS, render_checkout, validate_circuit_ir
from physics_workflow import PhysicsWorkflowError, verify_physics_workflow
from v05_golden_cases import build_golden_case


class V05CircuitIRTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image = ROOT / "examples" / "v05-v2-cot" / "schematic.svg"
        cls.intake, cls.circuit, cls.spec = build_golden_case("v2-cot", image_path=cls.image)

    def test_confirmed_ir_has_image_hash_dimensions_orientations_and_no_ambiguity(self):
        self.assertEqual(validate_circuit_ir(self.circuit, require_confirmation=True), [])
        self.assertEqual(self.circuit["source_image"]["width_px"], 960)
        self.assertEqual(self.circuit["source_image"]["height_px"], 540)
        self.assertTrue(all("orientation" in item for item in self.circuit["components"] if item["type"] != "comparator"))
        self.assertFalse(self.circuit["ambiguities"])

    def test_svg_checkout_is_deterministic_and_numbered(self):
        with tempfile.TemporaryDirectory() as td:
            first = Path(td) / "first.svg"
            second = Path(td) / "second.svg"
            render_checkout(self.circuit, self.image, first)
            render_checkout(self.circuit, self.image, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            text = first.read_text(encoding="utf-8")
            self.assertIn('data-component-id="QH"', text)
            self.assertIn('data-component-id="CMP"', text)
            self.assertIn('data-node-id="vo"', text)
            self.assertIn("N04:vo", text)

    def test_open_ambiguity_cannot_cross_confirmation_gate(self):
        bad = copy.deepcopy(self.circuit)
        bad["ambiguities"] = [{
            "id": "wire-7", "kind": "connectivity", "description": "crossing may be a junction",
            "blocking": True, "status": "OPEN",
        }]
        errors = validate_circuit_ir(bad, require_confirmation=True)
        self.assertTrue(any("ASK_USER_ONLY:OPEN_BLOCKING_AMBIGUITIES" in item for item in errors))

    def test_wrong_dimension_and_orientation_are_rejected(self):
        bad = copy.deepcopy(self.circuit)
        inductor = next(item for item in bad["components"] if item["id"] == "L")
        inductor["value"]["si_dimension"] = DIMENSIONS["F"]
        inductor["orientation"]["current_from"] = "missing"
        errors = validate_circuit_ir(bad, require_confirmation=True)
        self.assertTrue(any("FAIL_COMPONENT_DIMENSION:L" in item for item in errors))
        self.assertIn("FAIL_ORIENTATION_TERMINAL:L", errors)

    def test_comparator_polarity_must_match_the_confirmed_guard(self):
        bad = copy.deepcopy(self.circuit)
        comparator = next(item for item in bad["components"] if item["id"] == "CMP")
        comparator["parameters"]["guard_expression"] = "v_control-v_vo"
        errors = validate_circuit_ir(bad, require_confirmation=True)
        self.assertIn("FAIL_COMPARATOR_GUARD_POLARITY:CMP", errors)

    def test_floating_or_dangling_net_is_rejected(self):
        bad = copy.deepcopy(self.circuit)
        bad["nets"].append({"id": "floating", "aliases": [], "evidence_regions": []})
        errors = validate_circuit_ir(bad, require_confirmation=True)
        self.assertTrue(any("FAIL_DANGLING_NET" in item for item in errors))
        self.assertTrue(any("FAIL_FLOATING_SUBCIRCUIT" in item for item in errors))

    def test_hash_tampering_is_detected(self):
        bad = copy.deepcopy(self.circuit)
        bad["components"][0]["confidence"] = 0.5
        with self.assertRaises(PhysicsWorkflowError):
            verify_physics_workflow(bad, expected_state="TOPOLOGY_CONFIRMED")


if __name__ == "__main__":
    unittest.main()
