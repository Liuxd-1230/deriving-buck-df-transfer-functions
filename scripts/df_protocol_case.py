#!/usr/bin/env python3
"""Build and render v0.3 event-based DF protocol cases."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from df_model_classifier import classify_intake


class ProtocolCaseError(ValueError):
    """Raised when intake evidence is insufficient or unsupported."""


def _require_event_chain(events: Any) -> None:
    if not isinstance(events, list) or not events:
        raise ProtocolCaseError("switching_events is required; no final transfer function may be produced.")
    movable = [event for event in events if event.get("fixed_or_movable") == "movable"]
    if not movable:
        raise ProtocolCaseError("switching_events must identify a movable edge.")
    for event in movable:
        for field in ("equation", "edge_slope", "delta_edge"):
            if not event.get(field):
                raise ProtocolCaseError(f"switching_events.{field} is required for the movable edge.")
        if "=0" not in event["equation"].replace(" ", ""):
            raise ProtocolCaseError("switching_events.equation must state an F(...)=0 event.")


def build_protocol_case(intake: dict[str, Any]) -> dict[str, Any]:
    classification = classify_intake(intake)
    if classification["path"] == "UNSUPPORTED":
        raise ProtocolCaseError("Unsupported circuit: " + ", ".join(classification["unsupported_effects"]))
    if classification["path"] == "INCOMPLETE":
        raise ProtocolCaseError("Missing information: " + ", ".join(classification["missing_information"]))
    if classification["path"] == "KNOWN_MODEL":
        raise ProtocolCaseError("Registered models must use make-case; protocol derivation is not required.")

    events = deepcopy(intake.get("switching_events"))
    _require_event_chain(events)
    protocol_inputs = (
        "state_variables",
        "switching_state_equations",
        "steady_state_trajectory",
        "perturbation_paths",
        "sanity_checks",
    )
    missing_protocol = [field for field in protocol_inputs if not intake.get(field)]
    if missing_protocol:
        raise ProtocolCaseError("Missing DF reasoning steps: " + ", ".join(missing_protocol))
    df_relation = deepcopy(intake.get("df_relation"))
    if not isinstance(df_relation, dict) or not df_relation.get("form"):
        raise ProtocolCaseError("df_relation.form is required after edge perturbation.")
    if not df_relation.get("origin"):
        raise ProtocolCaseError("df_relation.origin provenance is required.")

    requested_mode = intake.get("mode", "derive-by-protocol")
    if requested_mode == "custom-unverified-df" or df_relation.get("origin") == "user-supplied":
        missing = [field for field in ("df_source", "event_equation", "valid_frequency")
                   if not intake.get(field)]
        if missing:
            raise ProtocolCaseError("Custom coefficients require: " + ", ".join(missing))
        level = "CUSTOM_COEFFICIENT_UNVERIFIED"
        claim = "CUSTOM_UNVERIFIED_DF"
        mode = "custom-unverified-df"
    else:
        level = "PROTOCOL_DERIVED_UNVERIFIED"
        claim = "UNVERIFIED_NEW_DF_MODEL"
        mode = "derive-by-protocol"

    return {
        "case_version": "0.3",
        "mode": mode,
        "target": intake["target"],
        "classification": classification,
        "assumptions_and_unsupported_effects": {
            "assumptions": ["single-phase", "CCM", "event-described control"],
            "unsupported_effects": classification["unsupported_effects"],
        },
        "state_variables": deepcopy(intake.get("state_variables", [])),
        "switching_state_equations": deepcopy(intake.get("switching_state_equations", {})),
        "steady_state_trajectory": intake.get("steady_state_trajectory", ""),
        "power_stage": deepcopy(intake.get("parameters", {})),
        "control_timing": deepcopy(intake.get("control_timing", {})),
        "switching_events": events,
        "comparator_inputs": deepcopy(intake.get("comparator_inputs", {})),
        "perturbation_paths": deepcopy(intake.get("perturbation_paths", {})),
        "df_relation": df_relation,
        "buck_power_stage_coupling": intake.get(
            "buck_power_stage_coupling",
            "Combine the event-derived switching-function relation with the CCM Buck power-stage equations.",
        ),
        "transfer_function": intake.get("transfer_function", "candidate; algebraic elimination pending"),
        "sanity_checks": deepcopy(intake.get("sanity_checks", [])),
        "validation_status": {
            "level": level,
            "claim": claim,
            "completed": deepcopy(intake.get("validation_completed", ["protocol-completeness"])),
            "missing": deepcopy(intake.get("validation_missing", ["switching-simulation", "paper-benchmark"])),
        },
        "provenance": deepcopy(intake.get("provenance", {"df_relation": df_relation["origin"]})),
    }


def render_protocol_report(case: dict[str, Any]) -> str:
    event_lines = []
    edge_lines = []
    for event in case["switching_events"]:
        event_lines.append(f"- `{event['name']}` ({event['fixed_or_movable']}): `{event['equation']}`")
        edge_lines.append(f"- Slope: `{event['edge_slope']}`; perturbation: `{event['delta_edge']}`")
    c = case["classification"]
    v = case["validation_status"]
    timing = case.get("control_timing", {})
    timing_line = f"Fixed timing: {timing.get('fixed', 'not supplied')}; variable timing: {timing.get('variable', 'not supplied')}"
    return "\n".join([
        "# DF protocol derivation", "",
        "## Model classification", "", f"- Path: `{c['path']}`", f"- Action: `{c['action']}`", "",
        "## Assumptions and unsupported effects", "", str(case["assumptions_and_unsupported_effects"]), "",
        "## State variables and switching states", "", str(case["state_variables"]),
        str(case["switching_state_equations"]), "",
        "## Steady-state trajectory", "", str(case["steady_state_trajectory"]), "",
        "## Switching event equation", "", *event_lines, "",
        "## Edge perturbation", "", timing_line, *edge_lines, "",
        "## Describing-function relation", "", f"`{case['df_relation']['form']}`",
        f"Equivalent-duty caveat: {case['df_relation'].get('duty_caveat', 'not supplied')}", "",
        "## Mapping to a_c/a_g/a_o/a_i", "", str({k: v for k, v in case["df_relation"].items() if k.startswith("a_")}), "",
        "## Buck power-stage coupling", "", str(case["buck_power_stage_coupling"]), "",
        "## Transfer function", "", str(case["transfer_function"]), "",
        "## Sanity checks", "", str(case["sanity_checks"]), "",
        "## Validation status", "", f"- Level: `{v['level']}`", f"- Claim: `{v['claim']}`",
        f"- Completed: {v['completed']}", f"- Missing: {v['missing']}", "",
        "## What is paper-derived vs newly derived", "", str(case["provenance"]), "",
    ])
