#!/usr/bin/env python3
"""Shared conservative validation and downgrade policy helpers."""

from __future__ import annotations

from typing import Any


NEAR_MODEL_SENSING_TYPES = {"unknown", "custom_sensing_network"}
UNREGISTERED_SENSING_VALIDATION = {"user_supplied", "measured", "unverified", "unknown"}
DOWNGRADED_LEVELS = {
    "NEAR_MODEL",
    "AUDIT_REQUIRED",
    "MODEL_ANALOGY_ONLY",
    "PROTOCOL_DERIVED_UNVERIFIED",
    "CHAIN_PARTIAL",
    "LOW_ORDER_APPROXIMATION",
    "TARGET_SEMANTICS_AMBIGUOUS",
    "REFERENCE_TARGET_SEMANTICS_UNCLEAR",
}


def sensing_layer_status(intake: dict[str, Any]) -> dict[str, Any]:
    sensing = intake.get("sensing_layer")
    if not isinstance(sensing, dict):
        return {
            "status": "MISSING",
            "registered": False,
            "validation_flags": ["ASK_USER_ONLY", "SENSING_LAYER_MISSING"],
        }
    layer_type = str(sensing.get("type", "unknown"))
    validation = str(sensing.get("validation", "unknown"))
    registered = validation == "registered"
    if layer_type in NEAR_MODEL_SENSING_TYPES or validation in UNREGISTERED_SENSING_VALIDATION:
        return {
            "status": "UNREGISTERED",
            "registered": False,
            "validation_flags": [
                "NEAR_MODEL",
                "AUDIT_REQUIRED",
                "MODEL_ANALOGY_ONLY",
                "PROTOCOL_DERIVED_UNVERIFIED",
            ],
        }
    return {
        "status": "REGISTERED" if registered else "UNVERIFIED",
        "registered": registered,
        "validation_flags": [] if registered else ["AUDIT_REQUIRED", "PROTOCOL_DERIVED_UNVERIFIED"],
    }


def is_user_intent(intent: str | None) -> bool:
    return (intent or "user-circuit-derivation") == "user-circuit-derivation"


def near_model_classification(intake: dict[str, Any], *, reason: str) -> dict[str, Any]:
    return {
        "topology": intake.get("topology", "unknown"),
        "conduction_mode": intake.get("conduction_mode", "unknown"),
        "phases": intake.get("phases", "unknown"),
        "control_family": intake.get("control_family", "unknown"),
        "unsupported_effects": [],
        "path": "NEAR_MODEL",
        "model_match": {"known_model": False, "model_id": None, "confidence": "low"},
        "action": "audit_required_before_registered_model",
        "validation_level": "PROTOCOL_DERIVED_UNVERIFIED",
        "validation_flags": [
            "NEAR_MODEL",
            "AUDIT_REQUIRED",
            "MODEL_ANALOGY_ONLY",
            "PROTOCOL_DERIVED_UNVERIFIED",
        ],
        "missing_information": [],
        "sensing_layer": intake.get("sensing_layer", {"type": "unknown"}),
        "reason": reason,
    }


def normalization_decision(
    *, formula_metadata: dict[str, Any], target_semantics: dict[str, Any]
) -> dict[str, Any]:
    fc_metadata = formula_metadata.get("Fc", {}) if isinstance(formula_metadata, dict) else {}
    includes_ri = bool(fc_metadata.get("includes_1_over_Ri"))
    target_input = str(target_semantics.get("input", "unknown"))
    if includes_ri and target_input == "voltage_control":
        return {
            "status": "PASS",
            "composition": "NO_EXTRA_RI_DIVISION",
            "blocking": False,
            "reason": "Fc already contains 1/Ri and the target input is voltage control.",
        }
    if includes_ri and target_input != "voltage_control":
        return {
            "status": "NORMALIZATION_AMBIGUOUS",
            "composition": "DO_NOT_REWRITE",
            "blocking": True,
            "reason": "Fc contains 1/Ri but target input semantics are not voltage_control.",
        }
    return {
        "status": "PASS",
        "composition": "NO_DOUBLE_RI_RISK_DETECTED",
        "blocking": False,
        "reason": "Formula metadata does not indicate an embedded 1/Ri normalization.",
    }


def validate_power_stage_claim(diagnostics: dict[str, Any]) -> dict[str, Any]:
    diagnosis = diagnostics.get("diagnosis")
    declared = bool(diagnostics.get("approximation_declared"))
    claims = set(diagnostics.get("claims", []))
    errors: list[str] = []
    if diagnosis == "LOW_ORDER_POWER_STAGE" and not declared:
        errors.append("LOW_ORDER_POWER_STAGE requires LOW_ORDER_APPROXIMATION metadata.")
    if diagnosis == "LOW_ORDER_POWER_STAGE" and (
        "FULL_POWER_STAGE_GVC" in claims or "FIGURE_REPRODUCED" in claims
    ):
        errors.append("Low-order paths cannot claim full power-stage Gvc or figure reproduction.")
    return {
        "status": "PASS" if not errors else "FAIL",
        "blocking": bool(errors),
        "errors": errors,
    }


def check_reference_claims(report: dict[str, Any]) -> dict[str, Any]:
    classification = report.get("final_classification")
    claims = set(report.get("claims", []))
    errors: list[str] = []
    if classification == "REFERENCE_TARGET_SEMANTICS_UNCLEAR" and "FIGURE_REPRODUCED" in claims:
        errors.append("REFERENCE_TARGET_SEMANTICS_UNCLEAR blocks FIGURE_REPRODUCED.")
    return {
        "status": "PASS" if not errors else "FAIL",
        "blocking": bool(errors),
        "errors": errors,
    }


def claim_restricted(validation_level: str | None) -> bool:
    return str(validation_level or "") in DOWNGRADED_LEVELS
