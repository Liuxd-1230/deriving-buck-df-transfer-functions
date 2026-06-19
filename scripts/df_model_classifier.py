#!/usr/bin/env python3
"""Classify Buck DF circuit intake without inventing missing event physics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from df_model_library import MODEL_SPECS
from preflight_intake import require_complete_intake
from fm_models import build_fm_model
from artifact_workflow import attach_workflow, verify_workflow
from schema_validation import validate_artifact
from formula_registry import model_specs


BASE_PARAMETERS = ("Vin", "Vo", "L", "C", "R", "rC")
MODEL_FAMILIES = {
    "cot-cm-li-lee-2010": "cot-current-mode",
    "cot-cm-external-ramp-tian-2015": "external-ramp-cot-current-mode",
    "rbcot-esr-lu-2023": "rbcot",
    "v2-cot-li-lee-2009": "v2-cot",
}
SAMPLED_PART_I = {"PCM", "VCM", "PVM", "VVM"}
SAMPLED_PART_II_CURRENT = {"C-COT", "C-COFT", "CCOT", "CCOFT"}
SAMPLED_PART_II_VOLTAGE = {"V-COT", "V-COFT", "VCOT", "VCOFT"}


def _unsupported(intake: dict[str, Any]) -> list[str]:
    effects: list[str] = []
    topology = str(intake.get("topology", "unknown")).lower()
    mode = str(intake.get("conduction_mode", "unknown")).upper()
    phases = intake.get("phases", "unknown")
    if topology not in {"buck", "buck-ccm", "unknown"}:
        effects.append("non-buck-topology")
    if mode == "DCM":
        effects.append("DCM")
    if mode in {"BCM", "BOUNDARY", "BOUNDARY CONDUCTION"}:
        effects.append("boundary-conduction")
    if intake.get("multiphase_overlap") or (isinstance(phases, int) and phases > 1 and intake.get("overlap", False)):
        effects.append("multiphase-overlap")
    for key, label in (("pulse_skipping", "pulse-skipping"), ("burst", "burst"),
                       ("nonlinear_current_limit", "nonlinear-current-limit"),
                       ("average_model_as_df", "average-model-as-df"),
                       ("requires_two_pulse_trains", "cot-two-pulse-train"),
                       ("dynamic_Fm_s", "dynamic-Fm-s")):
        if intake.get(key):
            effects.append(label)
    fm_result = build_fm_model(intake)
    if fm_result["status"].startswith("REJECT_"):
        effects.append(fm_result["status"])
    return effects


def _normalized_family(value: Any) -> str:
    text = str(value or "").upper().replace("_", "-").replace(" ", "-")
    aliases = {
        "CURRENT-MODE-COT": "C-COT",
        "CURRENT-MODE-CONSTANT-ON-TIME": "C-COT",
        "VOLTAGE-MODE-COT": "V-COT",
        "VOLTAGE-MODE-CONSTANT-ON-TIME": "V-COT",
    }
    return aliases.get(text, text)


def _sampled_data_part_family(intake: dict[str, Any]) -> str | None:
    family = _normalized_family(intake.get("control_family"))
    if family in SAMPLED_PART_I:
        return "SAMPLED_DATA_REGISTERED_PART_I_PCM_VCM_PVM_VVM"
    if family in SAMPLED_PART_II_CURRENT:
        return "SAMPLED_DATA_REGISTERED_PART_II_CCOT_CCOFT"
    if family in SAMPLED_PART_II_VOLTAGE:
        return "SAMPLED_DATA_REGISTERED_PART_II_VCOT_VCOFT"
    return None


def _missing_for_protocol(intake: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in ("target", "topology", "conduction_mode", "phases", "control_family"):
        if intake.get(field) in (None, "", "unknown"):
            missing.append(field)
    if not intake.get("switching_events"):
        missing.append("switching_events")
    if not intake.get("comparator_inputs"):
        missing.append("comparator_inputs")
    parameters = intake.get("parameters")
    if not isinstance(parameters, dict):
        missing.append("parameters")
    else:
        absent = [name for name in BASE_PARAMETERS if name not in parameters]
        if absent:
            missing.append("parameters:" + ",".join(absent))
        if "fs" not in parameters and "Ton" not in parameters:
            missing.append("parameters:fs-or-Ton")
    return missing


def classify_intake(intake: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(intake, dict):
        raise ValueError("Circuit intake must be a JSON object.")

    phases = intake.get("phases", "unknown")
    is_multiphase = isinstance(phases, int) and not isinstance(phases, bool) and phases > 1
    if is_multiphase:
        overlap = bool(intake.get("multiphase_overlap") or intake.get("overlap"))
        path = "MULTIPHASE_OVERLAP" if overlap else "MULTIPHASE_NONOVERLAP"
        code = "REJECT_MULTIPHASE_OVERLAP_V05" if overlap else "REJECT_MULTIPHASE_NONOVERLAP_V05"
        return {
            "topology": intake.get("topology", "unknown"),
            "conduction_mode": intake.get("conduction_mode", "unknown"),
            "phases": phases,
            "control_family": intake.get("control_family", "unknown"),
            "unsupported_effects": [code],
            "path": path,
            "model_match": {"known_model": False, "model_id": None, "confidence": "high"},
            "action": "PLANNED_REGISTERED_MODEL_V05",
            "validation_level": "REJECTED_UNSUPPORTED",
            "missing_information": [],
        }

    unsupported = _unsupported(intake)
    base = {
        "topology": intake.get("topology", "unknown"),
        "conduction_mode": intake.get("conduction_mode", "unknown"),
        "phases": intake.get("phases", "unknown"),
        "control_family": intake.get("control_family", "unknown"),
        "unsupported_effects": unsupported,
    }
    if unsupported:
        return {**base, "path": "UNSUPPORTED", "model_match": {"known_model": False,
                "model_id": None, "confidence": "high"}, "action": "reject_unsupported",
                "validation_level": "REJECTED_UNSUPPORTED", "missing_information": []}

    model_id = intake.get("model_id")
    modifications = intake.get("modifications") or []
    if model_id in MODEL_SPECS and not modifications:
        base.update({
            "topology": intake.get("topology", "buck"),
            "conduction_mode": intake.get("conduction_mode", "CCM"),
            "phases": intake.get("phases", 1),
            "control_family": intake.get("control_family", MODEL_FAMILIES[model_id]),
        })
        registered_path = (
            "DF_REGISTERED_DIRECT"
            if MODEL_SPECS[model_id]["interface"] == "direct-transfer"
            else "DF_REGISTERED_MULTIPORT"
        )
        return {**base, "path": registered_path, "model_id": model_id,
                "model_match": {"known_model": True,
                "model_id": model_id, "confidence": "high"}, "action": "use_registered_model",
                "validation_level": "PAPER_GROUNDED_PARTIAL", "missing_information": []}

    part_family = _sampled_data_part_family(intake)
    if part_family:
        target = intake.get("target_transfer") or intake.get("target")
        normalized_family = _normalized_family(intake.get("control_family"))
        part_i_model = (
            "yan-2022-part-i-voltage-buck"
            if normalized_family in {"PVM", "VVM"}
            else "yan-2022-part-i-pcm-buck"
        )
        model_id = {
            "SAMPLED_DATA_REGISTERED_PART_I_PCM_VCM_PVM_VVM": part_i_model,
            "SAMPLED_DATA_REGISTERED_PART_II_CCOT_CCOFT": "yan-2022-part-ii-ccot-buck-zero-ramp",
            "SAMPLED_DATA_REGISTERED_PART_II_VCOT_VCOFT": "yan-2022-part-ii-vcot-buck-zero-ramp",
        }[part_family]
        if target not in model_specs()[model_id]["supported_targets"]:
            return {**base, "path": "UNSUPPORTED", "model_id": model_id,
                    "model_match": {"known_model": True, "model_id": model_id, "confidence": "high"},
                    "action": "reject_unregistered_target",
                    "validation_level": "REJECTED_UNSUPPORTED",
                    "unsupported_effects": [f"TARGET_NOT_REGISTERED:{target}"],
                    "missing_information": []}
        return {**base, "path": "SAMPLED_DATA_REGISTERED",
                "part_family": part_family, "model_id": model_id,
                "target_transfer": target,
                "model_match": {"known_model": True, "model_id": model_id, "confidence": "medium"},
                "action": "use_sampled_data_registered_model",
                "validation_level": "SAMPLED_DATA_REGISTERED_PARTIAL",
                "missing_information": []}

    similar = intake.get("similar_model") or (model_id if model_id in MODEL_SPECS else None)
    missing = _missing_for_protocol(intake)
    if missing:
        return {**base, "path": "INCOMPLETE", "model_match": {"known_model": False,
                "model_id": similar, "confidence": "low"}, "action": "ask_for_missing_info",
                "validation_level": None, "missing_information": missing}

    if similar in MODEL_SPECS:
        path = "PROTOCOL_DERIVED_NEW"
        confidence = "medium"
    else:
        path = "PROTOCOL_DERIVED_NEW"
        confidence = "low"
    return {**base, "path": path, "model_match": {"known_model": False,
            "model_id": similar, "confidence": confidence}, "action": "derive_by_protocol",
            "validation_level": "PROTOCOL_DERIVED_UNVERIFIED", "missing_information": []}


def classify_intake_status(artifact: dict[str, Any]) -> dict[str, Any]:
    """Classify only after the mandatory intake gate has passed."""
    normalized = require_complete_intake(artifact)
    result = classify_intake(normalized)
    if artifact.get("intake_version") == "0.4":
        verify_workflow(artifact, expected_state="PREFLIGHT_INTAKE")
        result = {"classification_version": "0.4", **result}
        result = attach_workflow(
            result,
            state="MODEL_CLASSIFY",
            intent=artifact["workflow"]["intent"],
            predecessor=artifact,
        )
        validate_artifact(result, "classification.schema.json")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify a completed Buck DF intake artifact.")
    parser.add_argument("--intake-status", required=True)
    args = parser.parse_args()
    data = json.loads(Path(args.intake_status).read_text(encoding="utf-8"))
    print(json.dumps(classify_intake_status(data), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
