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
BENCHMARK_NAMES = {
    "tian2015_external_ramp",
    "li_lee2010_cot_cm",
    "li_lee2009_v2_rbcot",
    "lu2023_rbcot_loopgain",
}


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
                self.assertIn(results["status"], {"VERIFIED", "PARTIALLY_VERIFIED"})
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


if __name__ == "__main__":
    unittest.main()
