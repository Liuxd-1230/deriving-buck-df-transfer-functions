#!/usr/bin/env python3
"""Create the mandatory v0.3.1 intake gate artifact."""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from artifact_workflow import WorkflowError, attach_workflow, verify_workflow
from schema_validation import ArtifactSchemaError, validate_artifact
from validation_policy import is_user_intent


INTAKE_VERSION = "0.4"
REQUIRED_GROUPS = (
    "target_transfer",
    "operating_mode",
    "sampling_or_switching_event",
    "comparator_inputs",
    "parameters",
)
TLOOP_QUESTIONS = (
    "Where is the loop injection source?",
    "Which nodes define OUT/IN?",
    "Does the probe measure OUT/IN or -OUT/IN?",
    "What is feedback divider H?",
    "Is there any extra block between EA output and comparator input?",
    "Are current/voltage sense gains already included in Gvc?",
)
CORE_PARAMETER_GROUPS = (
    ("Vin",),
    ("Vo",),
    ("fs", "Ts", "Ton"),
    ("L",),
    ("C",),
    ("R", "Rload"),
    ("rC", "ESR"),
)


class IntakeGateError(ValueError):
    """Raised when a downstream command attempts to bypass preflight."""


def _text_normalization(text: str) -> dict[str, Any]:
    normalized: dict[str, Any] = {"request_text": text.strip()}
    lower = text.lower()

    target_matches = re.findall(r"\b(gvc|gvg|zout|tloop|ti|tv|tc)\b", lower)
    if target_matches:
        def normalize_target(value: str) -> str:
            normalized_value = value.replace("zout", "Zout").replace("tloop", "Tloop")
            if normalized_value not in {"Zout", "Tloop"}:
                normalized_value = normalized_value.capitalize()
            return normalized_value

        targets = []
        for match in target_matches:
            target = normalize_target(match)
            if target not in targets:
                targets.append(target)
        normalized["target_transfer"] = targets[0] if len(targets) == 1 else targets

    if "cot" in lower or "恒定导通" in text:
        if "谷值电压" in text or "valley voltage" in lower:
            normalized["control_family"] = "V-COT"
        elif "电流模" in text or "current-mode" in lower or "current mode" in lower:
            normalized["control_family"] = "C-COT"
        else:
            normalized["control_family"] = "COT"
    if re.search(r"\bbuck\b", lower):
        normalized["topology"] = "buck"
    if re.search(r"\bccm\b", lower):
        normalized["conduction_mode"] = "CCM"
    if re.search(r"\bdcm\b", lower):
        normalized["conduction_mode"] = "DCM"
    return normalized


def _normalized_intake(intake: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(intake)
    if "target_transfer" not in normalized and intake.get("target"):
        normalized["target_transfer"] = intake["target"]
    if "target" not in normalized and intake.get("target_transfer"):
        normalized["target"] = intake["target_transfer"]
    return normalized


def _missing_groups(normalized: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not normalized.get("target_transfer"):
        missing.append("target_transfer")

    operating_fields = ("topology", "conduction_mode", "phases", "control_family")
    if any(normalized.get(field) in (None, "", "unknown") for field in operating_fields):
        missing.append("operating_mode")

    events = normalized.get("switching_events")
    if not normalized.get("sampling_event") and not (isinstance(events, list) and events):
        missing.append("sampling_or_switching_event")

    comparators = normalized.get("comparator_inputs")
    if not isinstance(comparators, dict) or not comparators:
        missing.append("comparator_inputs")

    parameters = normalized.get("parameters")
    if not isinstance(parameters, dict) or any(
        not any(name in parameters for name in aliases) for aliases in CORE_PARAMETER_GROUPS
    ):
        missing.append("parameters")
    has_registered_or_protocol_contract = bool(normalized.get("model_id")) or isinstance(
        normalized.get("df_relation"), dict
    )
    if (
        is_user_intent(str(normalized.get("intent", "user-circuit-derivation")))
        and not has_registered_or_protocol_contract
        and not isinstance(normalized.get("sensing_layer"), dict)
    ):
        missing.append("sensing_layer")
    return missing


def _targets_include_tloop(normalized: dict[str, Any]) -> bool:
    target = normalized.get("target_transfer") or normalized.get("target")
    if isinstance(target, list):
        return any(str(item).lower() == "tloop" for item in target)
    return str(target).lower() == "tloop"


def _loop_break_complete(normalized: dict[str, Any]) -> bool:
    loop_break = normalized.get("loop_break")
    if not isinstance(loop_break, dict) or not loop_break.get("enabled"):
        return False
    required = (
        "injection_point",
        "return_point",
        "measured_quantity",
        "sign_convention",
        "forward_path",
        "feedback_path",
        "H",
    )
    return all(loop_break.get(name) not in (None, "", "unknown") for name in required)


def build_intake_status(*, intake: dict[str, Any] | None = None, text: str | None = None) -> dict[str, Any]:
    if (intake is None) == (text is None):
        raise IntakeGateError("Provide exactly one of structured intake or request text.")
    if intake is not None:
        if not isinstance(intake, dict):
            raise IntakeGateError("Structured intake must be a JSON object.")
        normalized = _normalized_intake(intake)
        source = "structured-intake"
    else:
        normalized = _text_normalization(text or "")
        source = "request-text"

    missing = _missing_groups(normalized)
    tloop_missing = _targets_include_tloop(normalized) and not _loop_break_complete(normalized)
    if tloop_missing and "loop_break" not in missing:
        missing.append("loop_break")
    complete = not missing
    status = "COMPLETE" if complete else ("INCOMPLETE_TLOOP_INTAKE" if tloop_missing else "INCOMPLETE")
    artifact = {
        "intake_version": INTAKE_VERSION,
        "source": source,
        "status": status,
        "missing": missing,
        "action": "CONTINUE_TO_CLASSIFICATION" if complete else "ASK_USER_ONLY",
        "normalized": normalized,
        **({"questions": list(TLOOP_QUESTIONS)} if tloop_missing else {}),
    }
    intent = str(normalized.get("intent", "user-circuit-derivation"))
    artifact = attach_workflow(artifact, state="PREFLIGHT_INTAKE", intent=intent)
    validate_artifact(artifact, "intake.schema.json")
    return artifact


def require_complete_intake(artifact: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(artifact, dict) or artifact.get("intake_version") not in {"0.3.1", "0.4"}:
        raise IntakeGateError("A v0.3.1 or v0.4 intake_status artifact is required.")
    if artifact.get("intake_version") == "0.4":
        try:
            validate_artifact(artifact, "intake.schema.json")
            verify_workflow(artifact, expected_state="PREFLIGHT_INTAKE")
        except (ArtifactSchemaError, WorkflowError) as exc:
            raise IntakeGateError(str(exc)) from exc
    if artifact.get("status") != "COMPLETE" or artifact.get("action") != "CONTINUE_TO_CLASSIFICATION":
        missing = artifact.get("missing", [])
        raise IntakeGateError("INCOMPLETE_INTAKE: ASK_USER_ONLY; missing: " + ", ".join(missing))
    normalized = artifact.get("normalized")
    if not isinstance(normalized, dict):
        raise IntakeGateError("intake_status.normalized must be an object.")
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the mandatory ESSF intake-status artifact.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="UTF-8 user-request text file.")
    source.add_argument("--intake", help="Structured intake JSON file.")
    parser.add_argument("--out", required=True, help="Output intake_status.json path.")
    args = parser.parse_args()

    if args.text:
        status = build_intake_status(text=Path(args.text).read_text(encoding="utf-8"))
    else:
        status = build_intake_status(
            intake=json.loads(Path(args.intake).read_text(encoding="utf-8"))
        )
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0 if status["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
