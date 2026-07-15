import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from circuit_ir import DIMENSIONS
from hybrid_mna import build_mode_dae
from parameter_sensitivity import _rebind
from v05_golden_cases import build_golden_case


def quantity(value, unit):
    return {"magnitude": value, "unit": unit, "si_dimension": DIMENSIONS[unit], "source": "registry_fixture"}


def orientation():
    return {"voltage_positive": "p", "voltage_negative": "n", "current_from": "p", "current_to": "n"}


def component(cid, kind, terminals, *, value=None, parameters=None):
    result = {
        "id": cid, "type": kind, "terminals": terminals, "bbox": [0.1, 0.1, 0.2, 0.2],
        "confidence": 1.0, "source_evidence": "unit stamp fixture",
    }
    if kind != "timer":
        result["orientation"] = orientation()
    if value is not None:
        result["value"] = value
    if parameters is not None:
        result["parameters"] = parameters
    return result


class V05ElementStampTests(unittest.TestCase):
    def test_controlled_sources_current_source_ramp_timer_and_lti_are_stamped(self):
        _, circuit, spec = build_golden_case("v2-cot")
        circuit = copy.deepcopy(circuit); spec = copy.deepcopy(spec)
        for net in ("aux", "vramp", "lti", "lti_tf"):
            circuit["nets"].append({"id": net, "aliases": [], "evidence_regions": []})
        circuit["components"].extend([
            component("IAUX", "current_source", {"p": "vo", "n": "gnd"}, value=quantity(0.0, "A"), parameters={"input": "load", "gain": 1.0, "dc": 0.0}),
            component("GCTRL", "vccs", {"p": "vo", "n": "gnd", "cp": "vo", "cn": "gnd"}, parameters={"gain": 1e-3}),
            component("ECTRL", "vcvs", {"p": "aux", "n": "gnd", "cp": "vo", "cn": "gnd"}, parameters={"gain": 0.1}),
            component("RAUX", "resistor", {"p": "aux", "n": "gnd"}, value=quantity(10.0, "ohm")),
            component("RAMP", "ramp", {"p": "vramp", "n": "gnd"}, parameters={"slope": 1e5, "active_modes": ["off"]}),
            component("RRAMP", "resistor", {"p": "vramp", "n": "gnd"}, value=quantity(1000.0, "ohm")),
            component("TIMER", "timer", {"reference": "gnd"}, parameters={"rate": 1.0, "active_modes": ["on"]}),
            component("FILTER", "lti_block", {"p": "lti", "n": "gnd", "cp": "vo", "cn": "gnd"}, parameters={"A": [[-1000.0]], "B": [[1000.0]], "C": [[1.0]], "D": [[0.0]]}),
            component("RLTI", "resistor", {"p": "lti", "n": "gnd"}, value=quantity(1000.0, "ohm")),
            component("FILTER_TF", "lti_block", {"p": "lti_tf", "n": "gnd", "cp": "vo", "cn": "gnd"}, parameters={"numerator": [1000.0], "denominator": [1.0, 1000.0]}),
            component("RLTI_TF", "resistor", {"p": "lti_tf", "n": "gnd"}, value=quantity(1000.0, "ohm")),
        ])
        spec["inputs"]["load"] = 0.0
        _rebind(circuit, spec)
        artifact = build_mode_dae(circuit, spec)
        provenance_types = {
            item["component_type"] for mode in artifact["modes"]
            for item in mode["component_provenance"] if "component_type" in item
        }
        self.assertTrue({"current_source", "vccs", "vcvs", "ramp", "timer", "lti_block"} <= provenance_types)
        self.assertEqual(artifact["modes"][0]["rank"]["dynamic"], 6)
        rational = next(item for item in artifact["component_inventory"] if item["id"] == "FILTER_TF")
        self.assertEqual(rational["parameters"]["realization_source"], "rational_transfer_function")
        self.assertEqual(rational["parameters"]["A"], [[-1000.0]])

    def test_diode_mode_assignment_uses_exact_on_off_constraints(self):
        _, circuit, spec = build_golden_case("v2-cot")
        circuit = copy.deepcopy(circuit); spec = copy.deepcopy(spec)
        low = next(item for item in circuit["components"] if item["id"] == "QL")
        low["id"] = "DLOW"; low["type"] = "diode"
        for mode in spec["modes"]:
            mode["switch_states"]["DLOW"] = mode["switch_states"].pop("QL")
        _rebind(circuit, spec)
        artifact = build_mode_dae(circuit, spec)
        laws = {
            mode["id"]: next(item for item in mode["equations"] if item.get("component_id") == "DLOW")
            for mode in artifact["modes"]
        }
        self.assertEqual(laws["on"]["state"], "OFF")
        self.assertIn("i_DLOW=0", laws["on"]["text"])
        self.assertEqual(laws["off"]["state"], "ON")
        self.assertEqual(laws["off"]["text"], "v_p-v_n=0")


if __name__ == "__main__":
    unittest.main()
