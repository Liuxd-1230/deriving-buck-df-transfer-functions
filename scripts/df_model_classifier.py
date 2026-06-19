#!/usr/bin/env python3
"""Classify Buck DF circuit intake without inventing missing event physics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from df_model_library import MODEL_SPECS
from preflight_intake import require_complete_intake


BASE_PARAMETERS = ("Vin", "Vo", "L", "C", "R", "rC")
MODEL_FAMILIES = {
    "cot-cm-li-lee-2010": "cot-current-mode",
    "cot-cm-external-ramp-tian-2015": "external-ramp-cot-current-mode",
    "rbcot-esr-lu-2023": "rbcot",
    "v2-cot-li-lee-2009": "v2-cot",
}


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
                       ("average_model_as_df", "average-model-as-df")):
        if intake.get(key):
            effects.append(label)
    return effects


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

    return classify_intake(require_complete_intake(artifact))


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify a completed Buck DF intake artifact.")
    parser.add_argument("--intake-status", required=True)
    args = parser.parse_args()
    data = json.loads(Path(args.intake_status).read_text(encoding="utf-8"))
    print(json.dumps(classify_intake_status(data), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
