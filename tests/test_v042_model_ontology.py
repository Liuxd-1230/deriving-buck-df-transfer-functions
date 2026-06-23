import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from df_model_classifier import classify_intake
from formula_registry import model_specs


def complete_parameters() -> dict:
    return {
        "Vin": 12,
        "Vo": 1.2,
        "fs": 300000,
        "L": 3e-7,
        "C": 560e-6,
        "R": 0.1,
        "rC": 0.006,
        "Ri": 0.01,
    }


class V042ModelOntologyTests(unittest.TestCase):
    def test_registered_models_expose_control_ontology_and_source_index(self) -> None:
        specs = model_specs()
        required = {
            "cot-cm-li-lee-2010": ("current-mode", "COT", "describing-function", "li-lee-2010"),
            "cot-cm-external-ramp-tian-2015": ("current-mode", "COT", "describing-function", "tian-2015"),
            "v2-cot-li-lee-2009": ("v2-cot", "COT", "direct-paper-transfer", "li-lee-2009"),
            "rbcot-esr-lu-2023": ("rbcot", "COT", "describing-function", "lu-2023"),
            "yan-2022-part-ii-vcot-buck-zero-ramp": ("voltage-mode", "COT", "sampled-data", "yan-2022-part-ii"),
        }
        for model_id, (control_mode, timing, method_family, source_key) in required.items():
            with self.subTest(model_id=model_id):
                spec = specs[model_id]
                ontology = spec.get("control_ontology")
                source_index = spec.get("source_index")
                self.assertIsInstance(ontology, dict)
                self.assertEqual(ontology["control_mode"], control_mode)
                self.assertEqual(ontology["timing"], timing)
                self.assertEqual(ontology["modeling_method"], method_family)
                self.assertIsInstance(source_index, dict)
                self.assertEqual(source_index["source_key"], source_key)

    def test_current_mode_cot_gvc_ri_sweep_selects_li_lee_2010_not_tian(self) -> None:
        result = classify_intake({
            "topology": "buck",
            "conduction_mode": "CCM",
            "phases": 1,
            "control_family": "current-mode COT",
            "target": "Gvc",
            "sweep": {"parameter": "Ri", "values": [0.0002, 0.001, 0.005]},
            "switching_events": [{"name": "valley", "equation": "Ri*iL-vc=0"}],
            "comparator_inputs": {"positive": "vc", "negative": "Ri*iL"},
            "parameters": complete_parameters(),
        })
        self.assertEqual(result["path"], "DF_REGISTERED_MULTIPORT")
        self.assertEqual(result["model_id"], "cot-cm-li-lee-2010")
        self.assertEqual(result["control_ontology"]["control_mode"], "current-mode")
        self.assertEqual(result["source_index"]["source_key"], "li-lee-2010")

    def test_external_ramp_current_mode_cot_records_external_ramp_source(self) -> None:
        result = classify_intake({
            "topology": "buck",
            "conduction_mode": "CCM",
            "phases": 1,
            "control_family": "current-mode COT",
            "target": "Gvc",
            "has_external_ramp": True,
            "external_ramp": {"slope_ratio": 0.2},
            "switching_events": [{"name": "valley", "equation": "Ri*iL+se*t-vc=0"}],
            "comparator_inputs": {"positive": "vc", "negative": "Ri*iL+external_ramp"},
            "parameters": complete_parameters() | {"se_ratio": 0.2},
        })
        self.assertEqual(result["path"], "DF_REGISTERED_MULTIPORT")
        self.assertEqual(result["model_id"], "cot-cm-external-ramp-tian-2015")
        self.assertEqual(result["control_ontology"]["ramp"], "external")
        self.assertEqual(result["source_index"]["source_key"], "tian-2015")

    def test_v2_cot_is_not_classified_as_yan_vcot_sampled_data(self) -> None:
        result = classify_intake({
            "topology": "buck",
            "conduction_mode": "CCM",
            "phases": 1,
            "control_family": "V2 COT",
            "target": "Gvc",
            "switching_events": [{"name": "valley", "equation": "vfb-vc=0"}],
            "comparator_inputs": {"positive": "vfb", "negative": "vc"},
            "parameters": complete_parameters(),
        })
        self.assertEqual(result["path"], "DF_REGISTERED_DIRECT")
        self.assertEqual(result["model_id"], "v2-cot-li-lee-2009")
        self.assertEqual(result["control_ontology"]["control_mode"], "v2-cot")
        self.assertNotEqual(result["model_id"], "yan-2022-part-ii-vcot-buck-zero-ramp")

    def test_rbcot_loop_gain_uses_return_ratio_model_not_plain_gvc(self) -> None:
        result = classify_intake({
            "topology": "buck",
            "conduction_mode": "CCM",
            "phases": 1,
            "control_family": "RBCOT",
            "target": "Tloop",
            "loop_break": {"enabled": True},
            "switching_events": [{"name": "ripple_valley", "equation": "vo_ripple-vc=0"}],
            "comparator_inputs": {"positive": "vo_ripple", "negative": "vc"},
            "parameters": complete_parameters(),
        })
        self.assertEqual(result["path"], "DF_REGISTERED_MULTIPORT")
        self.assertEqual(result["model_id"], "rbcot-esr-lu-2023")
        self.assertEqual(result["target_semantics"]["response_kind"], "return_ratio")
        self.assertEqual(result["source_index"]["source_key"], "lu-2023")


if __name__ == "__main__":
    unittest.main()
