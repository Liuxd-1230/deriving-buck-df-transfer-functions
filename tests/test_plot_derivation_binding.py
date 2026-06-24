import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPUTE_GVC = ROOT / "scripts" / "compute_gvc.py"


def derivation_with_coefficients(*, gvd_expression: str | None = None, plot_expression: str | None = None) -> dict:
    gvd = gvd_expression or "Vin*(1/(1/R + 1/(rC + 1/(s*C))))/(s*L + rL + 1/(1/R + 1/(rC + 1/(s*C))))"
    derivation = {
        "derivation_version": "0.4.5",
        "case_id": "plot-binding",
        "target_transfer": "Gvc",
        "target": {"name": "Gvc", "output": "vo_hat", "input": "vc_hat", "response_kind": "transfer_function"},
        "generated_by": "linear_system_transfer.py",
        "generated_expression": "Gvd*Kmod",
        "generated_expression_sha256": "0" * 64,
        "linear_equation_system": {
            "schema_version": "0.4.5",
            "case_id": "plot-binding",
            "symbols": ["s"],
            "unknowns": ["d_hat", "vo_hat"],
            "inputs": ["vc_hat"],
            "diagnostic_outputs": [],
            "variables": [
                {"name": "vc_hat", "role": "input", "quantity": "voltage", "unit_signature": "V"},
                {"name": "d_hat", "role": "unknown", "quantity": "duty", "unit_signature": "1"},
                {"name": "vo_hat", "role": "unknown", "quantity": "voltage", "unit_signature": "V"},
            ],
            "coefficient_definitions": [
                {
                    "symbol": "Kmod",
                    "expression": "D*(1-p)/(sf*Tsw) * (1 - p*exp(-s*Tsw))/(1-p)",
                    "from": "vc_hat",
                    "to": "d_hat",
                    "input_semantics": "control_signal",
                    "output_semantics": "duty",
                    "block_type": "closed_equivalent_block",
                    "unit_signature": "1/V",
                    "provenance": "protocol_derived_unverified",
                },
                {
                    "symbol": "Gvd",
                    "expression": gvd,
                    "from": "d_hat",
                    "to": "vo_hat",
                    "input_semantics": "duty",
                    "output_semantics": "voltage",
                    "block_type": "open_block",
                    "unit_signature": "V",
                    "provenance": "protocol_derived_unverified",
                },
            ],
            "parameter_units": {"rL": "Ohm", "L": "H", "C": "F", "R": "Ohm", "rC": "Ohm"},
            "blocks": [],
            "active_equations": [{"id": "eq", "block_id": "unused", "role": "active", "lhs": "vo_hat", "rhs": "Gvd*Kmod*vc_hat"}],
            "diagnostic_equations": [],
            "target": {"name": "Gvc", "output": "vo_hat", "input": "vc_hat", "response_kind": "transfer_function"},
            "approximation_policy": {"declared": False, "items": [], "valid_frequency": "not_declared"},
        },
        "steps": [{"index": 1, "object": "solver_generated_transfer", "dimension_signature": "V/V"}],
        "derivation_steps": [],
        "denominator_provenance": [],
        "approximation_policy": {"declared": False, "items": [], "valid_frequency": "not_declared"},
        "validation": {"level": "PROTOCOL_DERIVED_UNVERIFIED", "completed": [], "missing": []},
    }
    if plot_expression is not None:
        derivation["plot_expression"] = plot_expression
    return derivation


class PlotDerivationBindingTests(unittest.TestCase):
    def run_compute(self, derivation: dict):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "derivation.json"
            source.write_text(json.dumps(derivation), encoding="utf-8")
            out = root / "plots"
            result = subprocess.run(
                [sys.executable, str(COMPUTE_GVC), "--derivation", str(source), "--out-dir", str(out)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=60,
            )
            manifest = out / "plot_manifest.json"
            data = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else None
            return result, data

    def test_plot_manifest_hashes_derivation_and_coefficients(self) -> None:
        result, manifest = self.run_compute(derivation_with_coefficients())

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(manifest["status"], "PASS")
        self.assertEqual(manifest["source_expression"], "derivation.generated_expression")
        self.assertIn("derivation_sha256", manifest)
        self.assertIn("coefficient_expression_sha256", manifest)
        self.assertEqual(set(manifest["coefficient_expression_sha256"]), {"Kmod", "Gvd"})

    def test_plot_expression_mismatch_fails(self) -> None:
        result, _manifest = self.run_compute(derivation_with_coefficients(plot_expression="Gvd*Kmod/(1+Hs*Kmod)"))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL_PLOT_EXPRESSION_MISMATCH", result.stderr)

    def test_s_times_rl_power_stage_fails_dimension_check(self) -> None:
        result, _manifest = self.run_compute(derivation_with_coefficients(gvd_expression="Vin/(s*(L+rL)+1/(C*s))"))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL_DIMENSION_SIGNATURE_MISMATCH", result.stderr)


if __name__ == "__main__":
    unittest.main()
