import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPUTE_GVC = ROOT / "scripts" / "compute_gvc.py"


def derivation(gvd_expression: str) -> dict:
    return {
        "derivation_version": "0.4.5",
        "case_id": "gvd-dimension",
        "target_transfer": "Gvc",
        "target": {"name": "Gvc", "output": "vo_hat", "input": "vc_hat", "response_kind": "transfer_function"},
        "generated_by": "linear_system_transfer.py",
        "generated_expression": "Gvd*Kmod",
        "linear_equation_system": {
            "schema_version": "0.4.5",
            "case_id": "gvd-dimension",
            "symbols": ["s"],
            "unknowns": ["d_hat", "vo_hat"],
            "inputs": ["vc_hat"],
            "diagnostic_outputs": [],
            "parameters": {"Vin": 12, "R": 0.1, "rL": 0.0007, "L": 300e-9, "C": 400e-6, "rC": 0.0015, "D": 0.1, "p": 0.8101, "sf": 124900, "Ts": 2.0202e-6, "Tsw": 2.0202e-6},
            "parameter_units": {"rL": "Ohm", "R": "Ohm", "L": "H", "C": "F", "rC": "Ohm"},
            "coefficient_definitions": [
                {
                    "symbol": "Gvd",
                    "expression": gvd_expression,
                    "from": "d_hat",
                    "to": "vo_hat",
                    "input_semantics": "duty",
                    "output_semantics": "voltage",
                    "block_type": "open_block",
                    "unit_signature": "V",
                    "provenance": "protocol_derived_unverified",
                },
                {
                    "symbol": "Kmod",
                    "expression": "D*(1-p)/(sf*Ts) * (1 - p*exp(-s*Ts))/(1-p)",
                    "from": "vc_hat",
                    "to": "d_hat",
                    "input_semantics": "control_signal",
                    "output_semantics": "duty",
                    "block_type": "closed_equivalent_block",
                    "unit_signature": "1/V",
                    "provenance": "protocol_derived_unverified",
                },
            ],
            "blocks": [],
            "active_equations": [],
            "diagnostic_equations": [],
            "target": {"name": "Gvc", "output": "vo_hat", "input": "vc_hat", "response_kind": "transfer_function"},
        },
        "steps": [{"dimension_signature": "checked-by-linear-system-transfer"}],
        "derivation_steps": [],
        "denominator_provenance": [],
        "validation": {"level": "PROTOCOL_DERIVED_UNVERIFIED"},
    }


class PowerStageGvdDimensionTests(unittest.TestCase):
    def run_compute(self, artifact: dict):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "derivation.json"
            out = root / "plots"
            path.write_text(json.dumps(artifact), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(COMPUTE_GVC), "--derivation", str(path), "--out-dir", str(out)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=60,
            )
            manifest = out / "plot_manifest.json"
            return result, json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else None

    def test_canonical_gvd_dc_gain_is_vin_times_r_over_r_plus_rl(self) -> None:
        expr = "Vin*(1/(1/R + 1/(rC + 1/(s*C))))/(s*L + rL + 1/(1/R + 1/(rC + 1/(s*C))))"

        result, manifest = self.run_compute(derivation(expr))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertAlmostEqual(manifest["low_frequency_sanity"]["Gvd_dc_gain"], 12 * 0.1 / 0.1007, places=3)
        self.assertAlmostEqual(manifest["low_frequency_sanity"]["Gvc_dc_gain_db"], -0.95, delta=0.25)

    def test_missing_load_resistance_factor_fails_dc_gain_check(self) -> None:
        result, _manifest = self.run_compute(derivation("Vin/(R+rL)"))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL_POWER_STAGE_GVD_DC_GAIN_MISMATCH", result.stderr)

    def test_dcr_cannot_be_multiplied_by_s(self) -> None:
        result, _manifest = self.run_compute(derivation("Vin/(s*(L+rL)+1/(C*s))"))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL_DIMENSION_SIGNATURE_MISMATCH", result.stderr)


if __name__ == "__main__":
    unittest.main()
