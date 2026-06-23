#!/usr/bin/env python3
"""Conservative registered-model applicability checks."""

from __future__ import annotations

from typing import Any


CURRENT_SENSE_TYPES = {"direct_current_sense", "current_sense", "inductor_current_sense"}
OUTPUT_RIPPLE_TYPES = {"output_ripple", "output_ripple_sense", "capacitor_ripple", "esr_ripple"}
RC_STATE_TYPES = {"switch_node_rc", "sense_filter", "custom_sensing_network"}
ZERO_RAMP_REJECT_FLAGS = (
    "has_internal_ramp",
    "has_delay",
    "has_rc_injection",
    "has_filter_in_sense_path",
)


def _field(value: Any) -> str:
    return str(value or "").lower().replace("-", "_").replace(" ", "_")


def _target(intake: dict[str, Any]) -> str:
    target = intake.get("target_transfer") or intake.get("target") or ""
    if isinstance(target, list):
        return str(target[0]) if target else ""
    return str(target)


def _sensing(intake: dict[str, Any]) -> dict[str, Any]:
    value = intake.get("sensing_layer")
    return value if isinstance(value, dict) else {}


def _add_error(result: dict[str, Any], field: str, reason: str) -> None:
    result["errors"].append(reason)
    result["mismatched_fields"].append(field)


def check_model_applicability(intake: dict[str, Any], model_spec: dict[str, Any]) -> dict[str, Any]:
    """Return whether a user intake may use a registered model contract."""

    result: dict[str, Any] = {
        "status": "PASS",
        "blocking": False,
        "errors": [],
        "warnings": [],
        "matched_fields": [],
        "mismatched_fields": [],
    }
    ontology = model_spec.get("control_ontology") or {}
    sensing = _sensing(intake)
    has_sensing = bool(sensing)
    sensing_type = _field(sensing.get("type"))
    input_variable = _field(sensing.get("input_variable"))
    ripple_source = _field(ontology.get("ripple_source"))
    control_mode = _field(ontology.get("control_mode"))
    modeling_method = _field(ontology.get("modeling_method"))
    ramp = _field(ontology.get("ramp"))
    target = _target(intake)
    supported = set(model_spec.get("supported_targets") or [])
    supported.update(model_spec.get("loop_gain_targets") or [])

    if target and target not in supported:
        _add_error(result, "target_transfer", f"target {target} is not in registered supported_targets")
    else:
        result["matched_fields"].append("target_transfer")

    if target == "Tloop" and not isinstance(intake.get("loop_break"), dict):
        _add_error(result, "loop_break", "Tloop requires explicit loop_break semantics")

    if ripple_source in {"inductor_current", "sampled_current", "inductor_current_plus_linear_ramp"}:
        if not has_sensing:
            result["warnings"].append("sensing_layer not provided to applicability checker; preflight must gate user intakes")
        elif sensing_type not in CURRENT_SENSE_TYPES:
            _add_error(
                result,
                "sensing_layer.type",
                f"{ontology.get('control_mode')} registered model requires direct current sensing, got {sensing_type or 'missing'}",
            )
        else:
            result["matched_fields"].append("sensing_layer.type")
        if has_sensing and input_variable and input_variable not in {"il", "is", "inductor_current", "current"}:
            _add_error(result, "sensing_layer.input_variable", "current-mode registered model requires inductor-current input")

    if ripple_source in {"output_capacitor", "capacitor_esr"}:
        if not has_sensing:
            result["warnings"].append("sensing_layer not provided to applicability checker; preflight must gate user intakes")
        elif sensing_type not in OUTPUT_RIPPLE_TYPES:
            _add_error(
                result,
                "sensing_layer.type",
                f"{ontology.get('control_mode')} registered model requires output-capacitor ripple sensing, got {sensing_type or 'missing'}",
            )
        else:
            result["matched_fields"].append("sensing_layer.type")

    if has_sensing and control_mode in {"current_mode", "voltage_mode", "v2_cot", "rbcot"} and sensing_type in RC_STATE_TYPES:
        _add_error(result, "sensing_layer.type", "RC/custom sensing is not registered for this model topology")

    if modeling_method == "sampled_data" and ramp == "zero_ramp":
        if has_sensing and sensing_type in RC_STATE_TYPES:
            _add_error(result, "sensing_layer.type", "Yan zero-ramp sampled-data path cannot accept RC/custom sensing")
        if _field(intake.get("comparator_input_origin")) in {"switch_node_rc", "sense_filter"}:
            _add_error(result, "comparator_input_origin", "RC-derived comparator input cannot use Yan zero-ramp path")
        for flag in ZERO_RAMP_REJECT_FLAGS:
            if intake.get(flag):
                _add_error(result, flag, f"{flag} is outside the zero-ramp registered contract")

    comparator = intake.get("comparator_inputs") or {}
    if isinstance(comparator, dict):
        values = {_field(value) for value in comparator.values()}
        if ripple_source in {"inductor_current", "sampled_current"} and values and not any(
            item in values for item in {"is", "il", "isense", "inductor_current"}
        ):
            _add_error(result, "comparator_inputs", "current-mode comparator inputs must include sensed current")
        elif values:
            result["matched_fields"].append("comparator_inputs")

    if result["errors"]:
        result["status"] = "FAIL"
        result["blocking"] = True
    return result
