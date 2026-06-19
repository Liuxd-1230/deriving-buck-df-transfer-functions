#!/usr/bin/env python3
"""End-to-end tests for offline paper benchmark generation."""

from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


RUNNER = Path(__file__).with_name("run_benchmarks.py")
LEGACY_BENCHMARK_NAMES = {
    "tian2015_external_ramp",
    "li_lee2010_cot_cm",
    "li_lee2009_v2_rbcot",
    "lu2023_rbcot_loopgain",
}
SAMPLED_DATA_BENCHMARK_NAMES = {
    "yan_2022_part_i_pcm_buck",
    "yan_2022_part_ii_ccot_buck_zero_ramp",
    "yan_2022_part_ii_vcot_buck_zero_ramp",
    "yan_2022_part_ii_vcot_time_constant_trend",
}
BENCHMARK_NAMES = LEGACY_BENCHMARK_NAMES | SAMPLED_DATA_BENCHMARK_NAMES


class OfflineBenchmarkTests(unittest.TestCase):
    def test_all_benchmarks_generate_complete_finite_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            completed = subprocess.run(
                [sys.executable, str(RUNNER), "--all", "--output-root", str(root)],
                text=True,
                capture_output=True,
                check=False,
                timeout=120,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual({path.name for path in root.iterdir() if path.is_dir()}, BENCHMARK_NAMES)
            for name in BENCHMARK_NAMES:
                benchmark = root / name
                for filename in (
                    "params.json",
                    "generated_case.json",
                    "expected_key_values.json",
                    "results.json",
                    "bode_model.csv",
                    "bode.png",
                    "notes.md",
                ):
                    artifact = benchmark / filename
                    self.assertTrue(artifact.is_file(), str(artifact))
                    self.assertGreater(artifact.stat().st_size, 0, str(artifact))
                results = json.loads((benchmark / "results.json").read_text(encoding="utf-8"))
                self.assertIn(results["status"], {"VERIFIED", "PARTIALLY_VERIFIED", "SAMPLED_DATA_REGISTERED_PARTIAL"})
                with (benchmark / "bode_model.csv").open(encoding="utf-8", newline="") as handle:
                    rows = list(csv.DictReader(handle))
                self.assertGreater(len(rows), 100)
                for row in rows:
                    for value in row.values():
                        if value != "":
                            self.assertTrue(math.isfinite(float(value)))
                if name == "lu2023_rbcot_loopgain":
                    self.assertIn("pade_comparison_3p2m", results)
                    self.assertIn("esr_3p2m_pade_magnitude_db", rows[0])
                if name in SAMPLED_DATA_BENCHMARK_NAMES:
                    for filename in (
                        "intake.json",
                        "classification.json",
                        "proof_object.json",
                        "formula_origin.json",
                        "bode_summary.json",
                    ):
                        artifact = benchmark / filename
                        self.assertTrue(artifact.is_file(), str(artifact))
                    origin = json.loads((benchmark / "formula_origin.json").read_text(encoding="utf-8"))
                    self.assertEqual(origin["source"], "formula_registry.yaml")
                    self.assertFalse(origin["handwritten_formula_variants"])


if __name__ == "__main__":
    unittest.main()
