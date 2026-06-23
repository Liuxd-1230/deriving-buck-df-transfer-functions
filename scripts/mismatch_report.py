#!/usr/bin/env python3
"""Build conservative mismatch reports from reference-data semantics."""

from __future__ import annotations

from typing import Any


REQUIRED_REFERENCE_FIELDS = (
    "injection_point",
    "output_point",
    "sign_convention",
    "loop_break",
    "includes_sensing_layer",
)


def build_mismatch_report(spec: dict[str, Any]) -> dict[str, Any]:
    semantics = spec.get("measurement_semantics") or {}
    missing = [name for name in REQUIRED_REFERENCE_FIELDS if semantics.get(name) in (None, "", "unknown")]
    classification = "REFERENCE_TARGET_SEMANTICS_UNCLEAR" if missing else spec.get("final_classification", "UNKNOWN")
    return {
        "case_id": spec.get("case_id", "unknown"),
        "target": spec.get("target", "unknown"),
        "model_path": spec.get("model_path", "unknown"),
        "reference_source": spec.get("reference_source", "unknown"),
        "measurement_semantics": semantics,
        "key_points": spec.get("key_points", []),
        "region_classification": spec.get("region_classification", {
            "dc": "UNKNOWN",
            "resonance_region": "UNKNOWN",
            "zero_region": "UNKNOWN",
            "switching_limit_region": "UNKNOWN",
        }),
        "missing_semantics": missing,
        "final_classification": classification,
        "forbidden_claims": ["FIGURE_REPRODUCED"] if classification == "REFERENCE_TARGET_SEMANTICS_UNCLEAR" else [],
    }
