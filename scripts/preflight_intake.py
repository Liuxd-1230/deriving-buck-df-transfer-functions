#!/usr/bin/env python3
"""Create the mandatory v0.3.1 intake gate artifact."""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any


INTAKE_VERSION = "0.3.1"
REQUIRED_GROUPS = (
    "target_transfer",
    "operating_mode",
    "sampling_or_switching_event",
    "comparator_inputs",
    "parameters",
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

    target_match = re.search(r"\b(gvc|gvg|zout|tloop|ti|tv|tc)\b", lower)
    if target_match:
        normalized["target_transfer"] = target_match.group(1).replace("zout", "Zout").replace(
            "tloop", "Tloop"
        )
        if normalized["target_transfer"] not in {"Zout", "Tloop"}:
            normalized["target_transfer"] = normalized["target_transfer"].capitalize()

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
    return missing


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
    complete = not missing
    return {
        "intake_version": INTAKE_VERSION,
        "source": source,
        "status": "COMPLETE" if complete else "INCOMPLETE",
        "missing": missing,
        "action": "CONTINUE_TO_CLASSIFICATION" if complete else "ASK_USER_ONLY",
        "normalized": normalized,
    }


def require_complete_intake(artifact: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(artifact, dict) or artifact.get("intake_version") != INTAKE_VERSION:
        raise IntakeGateError("A v0.3.1 intake_status artifact is required.")
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
