import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_artifact.py"


class V04SchemaRuntimeTests(unittest.TestCase):
    def run_validator(self, schema: str, artifact: Path):
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--schema", schema, "--artifact", str(artifact)],
            cwd=ROOT, text=True, capture_output=True, timeout=30,
        )

    def test_v04_sampled_proof_and_classification_validate(self):
        proof = ROOT / "benchmarks" / "yan_2022_part_ii_ccot_buck_zero_ramp" / "proof_object.json"
        classification = ROOT / "benchmarks" / "yan_2022_part_ii_ccot_buck_zero_ramp" / "classification.json"
        self.assertTrue(VALIDATOR.is_file(), "runtime schema validator is missing")
        self.assertEqual(self.run_validator("proof_object.schema.json", proof).returncode, 0)
        self.assertEqual(self.run_validator("classification.schema.json", classification).returncode, 0)

    def test_v04_sampled_proof_missing_sampling_is_rejected(self):
        proof = json.loads((ROOT / "benchmarks" / "yan_2022_part_ii_ccot_buck_zero_ramp" / "proof_object.json").read_text(encoding="utf-8"))
        proof.pop("sampling")
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.json"
            path.write_text(json.dumps(proof), encoding="utf-8")
            result = self.run_validator("proof_object.schema.json", path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sampling", result.stdout + result.stderr)

    def test_v031_direct_proof_remains_schema_compatible(self):
        proof = ROOT / "tests" / "fixtures" / "valid_li_lee_2009_direct.json"
        self.assertEqual(self.run_validator("proof_object.schema.json", proof).returncode, 0)


if __name__ == "__main__":
    unittest.main()
