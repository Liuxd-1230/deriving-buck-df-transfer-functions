import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hybrid_linearization import HybridLinearizationError, _event_matrices
from hybrid_mna import HybridMNAError, build_mode_dae
from parameter_sensitivity import _rebind
from periodic_orbit import PeriodicOrbitError, _runtime_modes, solve_periodic_orbit
from physics_checker import PhysicsCheckerError, _apply_overrides
from physics_spec import confirm_physics_spec
from v05_golden_cases import build_golden_case
from circuit_ir import validate_circuit_ir


class V05NegativePathTests(unittest.TestCase):
    def setUp(self):
        _, self.circuit, self.spec = build_golden_case("v2-cot")

    def test_missing_initial_state_stops_before_orbit(self):
        circuit, spec = copy.deepcopy(self.circuit), copy.deepcopy(self.spec)
        spec.pop("initial_state")
        _rebind(circuit, spec)
        mode = build_mode_dae(circuit, spec)
        with self.assertRaisesRegex(PeriodicOrbitError, "ASK_USER_ONLY:INITIAL_STATE"):
            solve_periodic_orbit(mode, spec)

    def test_wrong_event_direction_fails_with_explicit_code(self):
        circuit, spec = copy.deepcopy(self.circuit), copy.deepcopy(self.spec)
        spec["mode_sequence"][1]["termination"]["direction"] = 1
        _rebind(circuit, spec)
        mode = build_mode_dae(circuit, spec)
        with self.assertRaisesRegex(PeriodicOrbitError, "FAIL_EVENT_NOT_FOUND"):
            solve_periodic_orbit(mode, spec)

    def test_wrong_mode_order_is_rejected_for_default_section(self):
        raw = copy.deepcopy(self.spec)
        raw.pop("workflow"); raw.pop("confirmation"); raw.pop("circuit_ir_sha256")
        raw["mode_sequence"] = list(reversed(raw["mode_sequence"]))
        raw["poincare_section"] = {
            "mode": "off", "position": "immediately_after_transition",
            "definition": "period_start_after_turn_on",
        }
        with self.assertRaisesRegex(HybridMNAError, "FAIL_EVENT_MODE_ORDER"):
            confirm_physics_spec(raw, self.circuit)

    def test_both_synchronous_switches_on_make_mode_singular(self):
        circuit, spec = copy.deepcopy(self.circuit), copy.deepcopy(self.spec)
        spec["modes"][0]["switch_states"]["QL"] = "ON"
        _rebind(circuit, spec)
        with self.assertRaisesRegex(HybridMNAError, "FAIL_IDEAL_VOLTAGE_SOURCE_LOOP"):
            build_mode_dae(circuit, spec)

    def test_parallel_ideal_voltage_sources_have_a_topology_failure_code(self):
        circuit, spec = copy.deepcopy(self.circuit), copy.deepcopy(self.spec)
        source = copy.deepcopy(next(item for item in circuit["components"] if item["id"] == "VG"))
        source["id"] = "VG_PARALLEL"
        source["parameters"] = {"dc": 12.0}
        circuit["components"].append(source)
        _rebind(circuit, spec)
        with self.assertRaisesRegex(HybridMNAError, "FAIL_IDEAL_VOLTAGE_SOURCE_LOOP"):
            build_mode_dae(circuit, spec)

    def test_tloop_without_loop_break_is_rejected_at_second_confirmation(self):
        raw = copy.deepcopy(self.spec)
        raw.pop("workflow"); raw.pop("confirmation"); raw.pop("circuit_ir_sha256")
        raw["target"] = {"name": "Tloop", "input": "uc", "output": "vo", "response_kind": "return_ratio"}
        with self.assertRaisesRegex(HybridMNAError, "FAIL_TLOOP_REQUIRES_LOOP_BREAK"):
            confirm_physics_spec(raw, self.circuit)

    def test_zout_requires_an_explicit_disturbance_sign_scale(self):
        raw = copy.deepcopy(self.spec)
        raw.pop("workflow"); raw.pop("confirmation"); raw.pop("circuit_ir_sha256")
        raw["target"] = {"name": "Zout", "input": "uc", "output": "vo", "response_kind": "transfer_function"}
        with self.assertRaisesRegex(HybridMNAError, "ASK_USER_ONLY:ZOUT_DISTURBANCE_SIGN"):
            confirm_physics_spec(raw, self.circuit)

    def test_duplicate_feedback_paths_are_rejected(self):
        raw = copy.deepcopy(self.spec)
        raw.pop("workflow"); raw.pop("confirmation"); raw.pop("circuit_ir_sha256")
        raw["loop_break"] = {"feedback_paths": [["CMP"], ["CMP", "QH"]]}
        with self.assertRaisesRegex(HybridMNAError, "FAIL_DUPLICATE_FEEDBACK_PATH"):
            confirm_physics_spec(raw, self.circuit)

    def test_near_grazing_saltation_is_not_regularised_silently(self):
        mode = build_mode_dae(self.circuit, self.spec)
        orbit = solve_periodic_orbit(mode, self.spec)
        modes = _runtime_modes(mode)
        event = copy.deepcopy(orbit["events"][1])
        event["Fdot"] = 0.0
        interval = orbit["mode_intervals"][1]
        with self.assertRaisesRegex(HybridLinearizationError, "FAIL_EVENT_NOT_TRANSVERSE"):
            _event_matrices(
                event, modes[event["from_mode"]], modes[event["to_mode"]],
                __import__("numpy").asarray(interval["end_reduced_before_reset"]),
                __import__("numpy").asarray(interval["end_reduced"]),
                __import__("numpy").asarray([orbit["inputs"][name] for name in mode["inputs"]]),
            )

    def test_non_postsolve_override_is_forbidden(self):
        spec = copy.deepcopy(self.spec)
        spec["overrides"] = [{"check_code": "FAIL_EVENT_NOT_TRANSVERSE", "reason": "ignore", "confirmed_by": "user"}]
        with self.assertRaisesRegex(PhysicsCheckerError, "FAIL_OVERRIDE_NOT_ALLOWED"):
            _apply_overrides([{"code": "FAIL_EVENT_NOT_TRANSVERSE", "status": "FAIL"}], spec)

    def test_reverse_current_orbit_is_rejected_by_ccm_gate(self):
        circuit, spec = copy.deepcopy(self.circuit), copy.deepcopy(self.spec)
        load = next(item for item in circuit["components"] if item["id"] == "RLOAD")
        load["value"]["magnitude"] = 1.0
        _rebind(circuit, spec)
        mode = build_mode_dae(circuit, spec)
        orbit = solve_periodic_orbit(mode, spec)
        ccm = next(item for item in orbit["checks"] if item["code"] == "CCM_MINIMUM_CURRENT")
        self.assertEqual(ccm["status"], "FAIL")
        self.assertLessEqual(ccm["value"], 0.0)

    def test_explicit_regularization_is_marked_diagnostic(self):
        circuit, spec = copy.deepcopy(self.circuit), copy.deepcopy(self.spec)
        spec["modes"][0]["switch_states"]["QL"] = "ON"
        _rebind(circuit, spec)
        artifact = build_mode_dae(circuit, spec, regularization_epsilon=1e-6)
        self.assertEqual(artifact["regularization"]["validation_status"], "REGULARIZED_DIAGNOSTIC_UNVERIFIED")
        self.assertEqual(artifact["regularization"]["epsilon"], 1e-6)


if __name__ == "__main__":
    unittest.main()
