import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_benchmarks.py"


class SampledDataBenchmarkTrendTests(unittest.TestCase):
    def test_vcot_time_constant_trend_preserves_yan_boundary_direction(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = subprocess.run(
                [sys.executable, str(RUNNER), "--benchmark", "yan_2022_part_ii_vcot_time_constant_trend", "--output-root", str(root)],
                cwd=ROOT, text=True, capture_output=True, timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            trend = json.loads((root / "yan_2022_part_ii_vcot_time_constant_trend" / "expected_trends.json").read_text(encoding="utf-8"))
            self.assertEqual(trend["criterion"], "rC*C > T0/2")
            self.assertEqual(trend["increase_rC"], "stability_margin_increases")
            self.assertEqual(trend["increase_C"], "stability_margin_increases")
            self.assertEqual(trend["increase_Ton"], "stability_margin_decreases")
            results = json.loads((root / "yan_2022_part_ii_vcot_time_constant_trend" / "results.json").read_text(encoding="utf-8"))
            self.assertTrue(results["trend_checks"]["increase_rC"])
            self.assertTrue(results["trend_checks"]["increase_C"])
            self.assertTrue(results["trend_checks"]["increase_Ton"])

    def test_yan_benchmarks_emit_gvc_and_tloop_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in (
                "yan_2022_part_ii_ccot_buck_zero_ramp",
                "yan_2022_part_ii_vcot_buck_zero_ramp",
            ):
                result = subprocess.run(
                    [sys.executable, str(RUNNER), "--benchmark", name, "--output-root", str(root)],
                    cwd=ROOT, text=True, capture_output=True, timeout=120,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

            ccot = root / "yan_2022_part_ii_ccot_buck_zero_ramp"
            vcot = root / "yan_2022_part_ii_vcot_buck_zero_ramp"
            ccot_summary = json.loads((ccot / "bode_summary.json").read_text(encoding="utf-8"))
            vcot_summary = json.loads((vcot / "bode_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(ccot_summary["targets"], ["Tloop"])
            self.assertEqual(ccot_summary["results"]["Tloop"]["stability_margins_status"], "APPLICABLE_RETURN_RATIO")
            self.assertTrue((ccot / "Tloop_bode.csv").is_file())
            self.assertEqual(vcot_summary["targets"], ["Gvc"])
            self.assertEqual(vcot_summary["results"]["Gvc"]["stability_margins_status"], "NOT_APPLICABLE_NON_RETURN_RATIO")
            self.assertTrue((vcot / "Gvc_bode.png").is_file())


if __name__ == "__main__":
    unittest.main()
