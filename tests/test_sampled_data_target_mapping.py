import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sampled_modulator import build_target_mapping


class SampledDataTargetMappingTests(unittest.TestCase):
    def test_registered_direct_output_maps_directly(self):
        mapping = build_target_mapping(
            available_outputs=["Gm", "Ti", "Tc"],
            requested_target="Gm",
            rules={"Gm": "sampled-data modulator output"},
        )
        self.assertEqual(mapping["mapping_status"], "REGISTERED_DIRECT")
        self.assertEqual(mapping["requested_target"], "Gm")

    def test_registered_derived_target_records_rule(self):
        mapping = build_target_mapping(
            available_outputs=["Gm", "Ti", "Tc"],
            requested_target="Tc",
            rules={"Tc": "Tc=Ti/(1+Ti)"},
        )
        self.assertEqual(mapping["mapping_status"], "REGISTERED_DERIVED")
        self.assertEqual(mapping["mapping_rule"], "Tc=Ti/(1+Ti)")

    def test_unsupported_target_is_not_renamed_to_tc_or_tloop(self):
        mapping = build_target_mapping(
            available_outputs=["Gm", "Ti", "Tc"],
            requested_target="Gvc",
            rules={"Tc": "Tc=Ti/(1+Ti)"},
        )
        self.assertEqual(mapping["mapping_status"], "UNSUPPORTED")
        self.assertEqual(mapping["requested_target"], "Gvc")


if __name__ == "__main__":
    unittest.main()
