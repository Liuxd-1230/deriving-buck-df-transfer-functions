#!/usr/bin/env python3
"""Check completeness and honesty of v0.3 DF derivation evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


FAILURE_ORDER = (
    "FAIL_UNSUPPORTED_TOPOLOGY",
    "FAIL_FALSE_DF",
    "FAIL_FALSE_VERIFICATION_CLAIM",
    "FAIL_MISSING_DF_SOURCE",
    "FAIL_MISSING_EVENT",
    "FAIL_MISSING_EDGE_PERTURBATION",
)


def _result(status: str, errors: list[str], warnings: list[str], checks: dict[str, bool]) -> dict[str, Any]:
    return {"status": status, "errors": errors, "warnings": warnings, "checks": checks}


def check_protocol_case(case: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, bool] = {}
    failures: set[str] = set()

    classification = case.get("classification", {})
    path = classification.get("path")
    unsupported = classification.get("unsupported_effects", [])
    checks["classification_declared"] = path in {
        "KNOWN_MODEL", "NEAR_MODEL", "NEW_MODEL",
        "DF_REGISTERED_DIRECT", "DF_REGISTERED_MULTIPORT", "PROTOCOL_DERIVED_NEW",
        "UNSUPPORTED",
    }

    if path == "UNSUPPORTED" or any(effect in unsupported for effect in
            ("multiphase-overlap", "DCM", "pulse-skipping", "burst", "nonlinear-current-limit")):
        failures.add("FAIL_UNSUPPORTED_TOPOLOGY")
        errors.append("The case uses an explicitly unsupported topology or operating behavior.")

    if case.get("method") == "average-model" or "average-model-as-df" in unsupported:
        failures.add("FAIL_FALSE_DF")
        errors.append("An average model is being represented as a describing function.")

    if path in {"KNOWN_MODEL", "DF_REGISTERED_DIRECT", "DF_REGISTERED_MULTIPORT"} and not failures:
        return _result("PASS_KNOWN_MODEL", errors, warnings, checks)

    events = case.get("switching_events")
    has_event = isinstance(events, list) and bool(events) and any(
        "=0" in str(event.get("equation", "")).replace(" ", "") for event in events
    )
    checks["event_equation"] = has_event
    if not has_event:
        failures.add("FAIL_MISSING_EVENT")
        errors.append("No explicit F(...)=0 switching event was found.")

    movable = [] if not isinstance(events, list) else [e for e in events if e.get("fixed_or_movable") == "movable"]
    has_delta = bool(movable) and all(
        e.get("edge_slope") and e.get("delta_edge") and
        "delta" in str(e["delta_edge"]).lower() and "fdot" in str(e["delta_edge"]).lower()
        for e in movable
    )
    checks["movable_edge"] = bool(movable)
    checks["edge_perturbation"] = has_delta
    if has_event and not has_delta:
        failures.add("FAIL_MISSING_EDGE_PERTURBATION")
        errors.append("The movable edge lacks slope or delta_t=-delta_F/Fdot evidence.")

    timing = case.get("control_timing", {})
    checks["timing_declared"] = isinstance(timing, dict) and bool(timing.get("fixed"))
    if has_event and not checks["timing_declared"]:
        warnings.append("Fixed/variable Ton, Toff, or period timing is not declared.")

    protocol_fields = {
        "state_variables": "State variables are missing.",
        "switching_state_equations": "The switch-state equations are missing.",
        "steady_state_trajectory": "The steady-state trajectory is missing.",
        "perturbation_paths": "Perturbation paths are missing.",
        "buck_power_stage_coupling": "Buck power-stage coupling is missing.",
        "transfer_function": "The candidate transfer-function step is missing.",
        "sanity_checks": "Sanity checks are missing.",
    }
    for field, warning in protocol_fields.items():
        checks[field] = bool(case.get(field))
        if not checks[field]:
            warnings.append(warning)

    relation = case.get("df_relation", {})
    checks["df_relation"] = isinstance(relation, dict) and bool(relation.get("form"))
    checks["duty_caveat"] = isinstance(relation, dict) and bool(relation.get("duty_caveat"))
    if not checks["df_relation"]:
        errors.append("No a_* mapping or direct-transfer DF relation is present.")
    if not checks["duty_caveat"]:
        warnings.append("The report does not distinguish equivalent switching perturbation from low-frequency duty.")

    provenance = case.get("provenance") or (relation.get("origin") if isinstance(relation, dict) else None)
    checks["provenance"] = bool(provenance)
    if not provenance:
        warnings.append("DF component provenance is missing.")

    if case.get("mode") == "custom-unverified-df" or (isinstance(relation, dict) and relation.get("origin") == "user-supplied"):
        required = (case.get("df_source"), case.get("event_equation"), case.get("valid_frequency"))
        if not all(required):
            failures.add("FAIL_MISSING_DF_SOURCE")
            errors.append("User-supplied coefficients require df_source, event_equation, and valid_frequency.")

    validation = case.get("validation_status", {})
    level = validation.get("level")
    claim = str(validation.get("claim", "")).lower()
    completed = set(validation.get("completed", []))
    missing = list(validation.get("missing", []))
    checks["validation_declared"] = bool(level)
    verified_claim = level == "PAPER_GROUNDED_VERIFIED" or ("verified" in claim and "unverified" not in claim)
    verification_evidence = {"paper-benchmark", "switching-simulation"}.issubset(completed)
    if verified_claim and not verification_evidence:
        failures.add("FAIL_FALSE_VERIFICATION_CLAIM")
        errors.append("A verified/correct claim lacks both paper benchmark and switching-simulation evidence.")

    if not failures and (missing or not {"symbolic", "dc-limit", "paper-benchmark", "switching-simulation"}.issubset(completed)):
        warnings.append("Validation is incomplete; unresolved items must remain explicit.")

    for status in FAILURE_ORDER:
        if status in failures:
            return _result(status, errors, warnings, checks)
    if warnings:
        return _result("WARNING_INCOMPLETE_VALIDATION", errors, warnings, checks)
    return _result("PASS_PROTOCOL_UNVERIFIED", errors, warnings, checks)


def check_report_text(text: str) -> dict[str, Any]:
    lower = text.lower()
    pseudo: dict[str, Any] = {
        "case_version": "0.3",
        "mode": "derive-by-protocol",
        "classification": {
            "path": "KNOWN_MODEL" if "known_model" in text and "new_model" not in text else "NEW_MODEL",
            "unsupported_effects": [],
        },
        "validation_status": {
            "level": "PROTOCOL_DERIVED_UNVERIFIED" if "protocol_derived_unverified" in lower else "",
            "claim": "UNVERIFIED_NEW_DF_MODEL" if "unverified_new_df_model" in lower else "",
            "completed": re.findall(r"(?:symbolic|dc-limit|paper-benchmark|switching-simulation)", lower),
            "missing": re.findall(r"missing[^\n]*", lower),
        },
    }
    event = re.search(
        r"\b(?:f\s*\([^\n)]*\)|f_(?:on|off|event|edge)(?:_[a-z0-9]+)*)"
        r"\s*=\s*(?:0|[^\n]*?=\s*0)\s*`?[.;,]?\s*$",
        lower,
        flags=re.MULTILINE,
    )
    delta = re.search(r"delta_t[^\n]*-?delta_f[^\n]*fdot", lower)
    if event:
        pseudo["switching_events"] = [{
            "name": "report_edge", "fixed_or_movable": "movable" if "movable" in lower else "unknown",
            "equation": event.group(0), "edge_slope": "Fdot_0" if "fdot" in lower else "",
            "delta_edge": delta.group(0) if delta else "",
        }]
    if "describing-function relation" in lower or "d_hat" in lower:
        pseudo["df_relation"] = {
            "form": "d_hat", "origin": "report-provenance" if "paper-derived vs newly derived" in lower else "",
            "duty_caveat": "equivalent switching perturbation" if "equivalent" in lower else "",
        }
    if "ton" in lower or "toff" in lower:
        pseudo["control_timing"] = {"fixed": "declared"}
    return check_protocol_case(pseudo)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a DF protocol case or derivation report.")
    commands = parser.add_subparsers(dest="command", required=True)
    report = commands.add_parser("check")
    report.add_argument("--report", required=True)
    structured = commands.add_parser("check-json")
    structured.add_argument("--case", required=True)
    args = parser.parse_args()
    if args.command == "check":
        result = check_report_text(Path(args.report).read_text(encoding="utf-8"))
    else:
        result = check_protocol_case(json.loads(Path(args.case).read_text(encoding="utf-8")))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["status"].startswith("FAIL_") else 0


if __name__ == "__main__":
    raise SystemExit(main())
