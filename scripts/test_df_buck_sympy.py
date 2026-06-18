#!/usr/bin/env python3
"""Regression tests for df_buck_sympy.py."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import sympy as sp


MODULE_PATH = Path(__file__).with_name("df_buck_sympy.py")
SPEC = importlib.util.spec_from_file_location("df_buck_sympy", MODULE_PATH)
assert SPEC and SPEC.loader
df = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = df
SPEC.loader.exec_module(df)


def base_case() -> dict:
    return {
        "name": "test-direct-modulator",
        "topology": "buck-ccm",
        "phases": 1,
        "df_source": "test fixture",
        "valid_frequency": "algebraic regression only",
        "modulator": {"a_c": "Fm", "a_g": "0", "a_o": "0", "a_i": "0"},
        "parameters": {},
        "targets": ["Gvc", "Gvg", "Zout"],
    }


class BuckDfTests(unittest.TestCase):
    def test_direct_modulator_matches_open_loop_plant(self) -> None:
        model = df.derive_model(base_case())
        fm = model["table"]["Fm"]
        self.assertEqual(sp.simplify(model["expressions"]["Gvc"] - fm * model["expressions"]["Gvd"]), 0)

    def test_input_and_output_impedance_signs(self) -> None:
        model = df.derive_model(base_case())
        self.assertEqual(sp.simplify(model["expressions"]["Gvg"] - model["expressions"]["Gvg_open"]), 0)
        self.assertEqual(sp.simplify(model["expressions"]["Zout"] - model["expressions"]["Zout_open"]), 0)

    def test_dc_identities(self) -> None:
        case = base_case()
        model = df.derive_model(case)
        report = df.build_check_report(case, model)
        self.assertTrue(all(report["structural_checks"].values()))

    def test_ideal_lc_plant_matches_canonical_denominator(self) -> None:
        model = df.derive_model(base_case())
        symbols = model["symbols"]
        s = symbols["s"]
        L = symbols["L"]
        C = symbols["C"]
        R = symbols["R"]
        Vg = symbols["Vg"]
        canonical = Vg / (L * C * s**2 + L * s / R + 1)
        actual = model["expressions"]["Gvd"].subs({symbols["rL"]: 0, symbols["rC"]: 0})
        self.assertEqual(sp.simplify(actual - canonical), 0)

    def test_multiphase_is_rejected(self) -> None:
        case = base_case()
        case["phases"] = 2
        with self.assertRaises(df.CaseError):
            df.derive_model(case)

    def test_tloop_requires_feedback(self) -> None:
        case = base_case()
        case["targets"].append("Tloop")
        with self.assertRaises(df.CaseError):
            df.derive_model(case)


class ModelCliTests(unittest.TestCase):
    def test_list_models_json_reports_only_df_registry(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(MODULE_PATH), "list-models", "--json"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(len(payload), 4)
        self.assertNotIn("rbcot-internal-ramp-huang-2025", payload)

    def test_make_case_generates_modulator_without_user_coefficients(self) -> None:
        parameters = {
            "Vin": 12.0,
            "Vo": 1.2,
            "fs": 300e3,
            "L": 300e-9,
            "C": 4480e-6,
            "R": 0.1,
            "rL": 0.0,
            "rC": 0.75e-3,
            "Ri": 10e-3,
            "se_ratio": 1.0,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            params_path = root / "params.json"
            output_path = root / "case.json"
            params_path.write_text(json.dumps(parameters), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(MODULE_PATH),
                    "make-case",
                    "--model",
                    "cot-cm-external-ramp-tian-2015",
                    "--params",
                    str(params_path),
                    "--out",
                    str(output_path),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            generated = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(set(generated["modulator"]), {"a_c", "a_g", "a_o", "a_i"})

    def test_make_case_rejects_huang_average_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            params_path = root / "params.json"
            output_path = root / "case.json"
            params_path.write_text("{}", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(MODULE_PATH),
                    "make-case",
                    "--model",
                    "rbcot-internal-ramp-huang-2025",
                    "--params",
                    str(params_path),
                    "--out",
                    str(output_path),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("average model", completed.stderr)

    def test_benchmark_subcommand_runs_all_offline_cases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(MODULE_PATH),
                    "benchmark",
                    "--all",
                    "--output-root",
                    directory,
                ],
                text=True,
                capture_output=True,
                check=False,
                timeout=120,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((Path(directory) / "lu2023_rbcot_loopgain" / "results.json").is_file())


if __name__ == "__main__":
    unittest.main()
