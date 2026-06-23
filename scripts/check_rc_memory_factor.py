#!/usr/bin/env python3
"""Check RC-derived comparator-ramp memory metadata."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any


RC_ORIGINS = {"switch_node_rc", "sense_filter"}


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _nested_payload(artifact: dict[str, Any]) -> dict[str, Any]:
    normalized = artifact.get("normalized")
    if isinstance(normalized, dict):
        return normalized
    intake = artifact.get("intake")
    if isinstance(intake, dict) and isinstance(intake.get("normalized"), dict):
        return intake["normalized"]
    return artifact


def _is_rc_case(payload: dict[str, Any]) -> bool:
    ramp = payload.get("comparator_ramp_model") if isinstance(payload.get("comparator_ramp_model"), dict) else {}
    sensing = payload.get("sensing_layer") if isinstance(payload.get("sensing_layer"), dict) else {}
    return (
        str(payload.get("comparator_input_origin", "")).lower() in RC_ORIGINS
        or str(ramp.get("type", "")).lower() == "rc_derived_state"
        or str(sensing.get("type", "")).lower() in RC_ORIGINS
        or str(sensing.get("network_type", "")).lower() == "rc_lowpass"
    )


def _looks_slope_only(kmod: str) -> bool:
    compact = kmod.replace(" ", "").lower()
    return bool(
        re.search(r"1/\(?ts\*abs\(?sfall\)?\)?", compact)
        or "1/(ts*local_slope)" in compact
        or "1/(ts*sfall)" in compact
    )


def _close(a: float, b: float, rel: float = 1e-6) -> bool:
    return abs(a - b) <= rel * max(abs(a), abs(b), 1.0)


def check_rc_memory_factor(artifact: dict[str, Any]) -> dict[str, Any]:
    payload = _nested_payload(artifact)
    if not _is_rc_case(payload):
        return {
            "status": "NOT_APPLICABLE",
            "blocking": False,
            "errors": [],
            "warnings": [],
            "reason": "comparator ramp is not declared as RC-derived state",
            "artifact": "proof_object.json",
        }

    ramp = payload.get("comparator_ramp_model") if isinstance(payload.get("comparator_ramp_model"), dict) else {}
    sensing = payload.get("sensing_layer") if isinstance(payload.get("sensing_layer"), dict) else {}
    switching = payload.get("switching") if isinstance(payload.get("switching"), dict) else {}
    parameters = payload.get("parameters") if isinstance(payload.get("parameters"), dict) else {}
    errors: list[str] = []
    warnings: list[str] = []

    R = _as_float(ramp.get("R", sensing.get("R")))
    C = _as_float(ramp.get("C", sensing.get("C")))
    tau = _as_float(ramp.get("tau", sensing.get("tau")))
    if R is None or C is None:
        errors.append("FAIL_MISSING_RC_TAU")
    elif tau is None or not _close(tau, R * C):
        errors.append("FAIL_MISSING_RC_TAU")

    Ts = _as_float(ramp.get("Ts", switching.get("Ts", parameters.get("Ts"))))
    p = _as_float(ramp.get("p"))
    if p is None and Ts is not None and tau is not None:
        p = math.exp(-Ts / tau)
    if p is None:
        errors.append("FAIL_MISSING_RC_MEMORY_FACTOR")

    kmod = str(ramp.get("Kmod", ramp.get("kmod", "")))
    if _looks_slope_only(kmod) or not ramp.get("memory_treatment"):
        errors.append("FAIL_RC_DERIVED_RAMP_SLOPE_ONLY")

    sf_source = str(ramp.get("sf_source", ""))
    sf = _as_float(ramp.get("sf"))
    if sf_source == "V0_over_tau":
        V0 = _as_float(ramp.get("V0"))
        if V0 is None or tau is None or sf is None or not _close(sf, V0 / tau, rel=1e-3):
            errors.append("FAIL_INCONSISTENT_RC_SLOPE_DEFINITION")
        if ramp.get("measured_average_falling_slope") is not None:
            errors.append("FAIL_INCONSISTENT_RC_SLOPE_DEFINITION")
    if ramp.get("measured_average_falling_slope") is not None and sf_source not in {
        "measured_average_falling_slope",
        "",
    }:
        errors.append("FAIL_INCONSISTENT_RC_SLOPE_DEFINITION")

    if ramp.get("borrowed_approximation"):
        warnings.append("WARN_BORROWED_ON_TIME_PAIR_APPROXIMATION")
    if "1-exp(-s*ton)" not in kmod.lower().replace(" ", "") and "z^-1" in kmod:
        warnings.append("WARN_LOW_FREQUENCY_AVERAGED_KMOD")

    status = "FAIL" if errors else ("WARN" if warnings else "PASS")
    return {
        "status": status,
        "blocking": bool(errors),
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "validation_level": "PROTOCOL_DERIVED_UNVERIFIED",
        "claims_allowed": ["PROTOCOL_DERIVED_UNVERIFIED", "LOW_FREQUENCY_AVERAGED_KMOD"],
        "reason": "; ".join(sorted(set(errors + warnings))) or "RC memory treatment metadata is present",
        "artifact": "proof_object.json",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check RC-derived comparator-ramp memory treatment.")
    parser.add_argument("--artifact", required=True)
    args = parser.parse_args()
    artifact = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
    result = check_rc_memory_factor(artifact)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"PASS", "WARN", "NOT_APPLICABLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
