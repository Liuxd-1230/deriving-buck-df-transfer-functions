#!/usr/bin/env python3
"""v0.4 zero-ramp Fm contracts for sampled-data COT/COFT models."""

from __future__ import annotations

from typing import Any


HARD_REJECTIONS = (
    ("has_external_ramp", "REJECT_DYNAMIC_FM_REQUIRED_V05"),
    ("has_internal_ramp", "REJECT_INTERNAL_RAMP_NOT_REGISTERED"),
    ("has_delay", "REJECT_DELAY_NOT_REGISTERED"),
    ("has_rc_injection", "REJECT_RC_INJECTION_NOT_REGISTERED"),
    ("has_filter_in_sense_path", "REJECT_SENSE_FILTER_NOT_REGISTERED"),
)


def _reject(status: str) -> dict[str, Any]:
    return {
        "status": status,
        "severity": "hard_fail",
        "message": status.replace("_", " ").lower(),
    }


def build_fm_model(spec: dict[str, Any]) -> dict[str, Any]:
    """Build the v0.4 zero-ramp constant Fm object or return a hard rejection.

    v0.4 intentionally supports only zero-ramp sampled-data registered models.
    External ramp, internal ramp, delay, RC injection, and sense-filter effects
    require dynamic Fm(s) or extra registered contracts planned for v0.5.
    """

    if not isinstance(spec, dict):
        return _reject("REJECT_INVALID_FM_SPEC")
    for flag, status in HARD_REJECTIONS:
        if spec.get(flag):
            return _reject(status)

    control = str(spec.get("control_family", "")).upper().replace("_", "-")
    parameters = spec.get("parameters") if isinstance(spec.get("parameters"), dict) else {}
    ts = parameters.get("Ts") or parameters.get("Tsw")
    expression = "1/((m2-m1)*Ts/2)"
    depends_on = ["m1", "m2", "Ts"]
    if "COFT" in control:
        expression = "1/((m1-m2)*Ts/2)"
    if not ts and "Ts" not in parameters:
        # Keep symbolic expression valid; caller can bind Ts later.
        ts = "Ts"
    return {
        "status": "OK",
        "severity": "none",
        "Fm": {
            "type": "constant",
            "expression": expression,
            "origin": "sampled_data_derivation",
            "depends_on": depends_on,
            "dirichlet_reference": "sampling.dirichlet_value",
            "derivation_steps": [
                "sample feedback perturbation at sampling.dirichlet_value",
                "derive d1_hat / sampled_variable_hat using zero-ramp slopes",
            ],
        },
    }
