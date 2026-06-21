#!/usr/bin/env python3
"""COT/COFT two-pulse-train contract for v0.4 sampled-data models."""

from __future__ import annotations

from typing import Any


def build_cot_pulse_structure(spec: dict[str, Any]) -> dict[str, Any]:
    control = str(spec.get("control_family", "C-COT")).upper().replace("_", "-")
    fixed = str(spec.get("fixed_interval") or ("Toff" if "COFT" in control else "Ton"))
    if "COFT" in control:
        pulse_type = "COFT_TWO_PULSE_TRAINS"
        t0 = "Toff"
    else:
        pulse_type = "COT_TWO_PULSE_TRAINS"
        t0 = "Ton"
    if fixed.lower() in {"toff", "off"}:
        t0 = "Toff"
    if fixed.lower() in {"ton", "on"}:
        t0 = "Ton"
    return {
        "type": pulse_type,
        "d1": "narrow pulse train at each sampling instant",
        "d2": f"delayed inverse narrow pulse train after {t0}",
        "relation": f"d2(t)=-d1(t-{t0})",
        "frequency_factor": f"1-exp(-s*{t0})",
        "T0": t0,
    }
