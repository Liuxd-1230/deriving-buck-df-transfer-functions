#!/usr/bin/env python3
"""Hash-linked ESSF artifact workflow metadata."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


WORKFLOW_VERSION = "0.4"
INTENTS = {"demo", "paper-benchmark", "user-circuit-derivation"}
STATE_PREDECESSOR = {
    "PREFLIGHT_INTAKE": None,
    "MODEL_CLASSIFY": "PREFLIGHT_INTAKE",
    "FORMULA_BINDING": "MODEL_CLASSIFY",
    "DERIVATION": "FORMULA_BINDING",
    "CHECKERS": "DERIVATION",
    "REPORT": "CHECKERS",
}
ARTIFACT_TYPES = {
    "PREFLIGHT_INTAKE": "intake_status",
    "MODEL_CLASSIFY": "classification",
    "FORMULA_BINDING": "proof_object",
    "DERIVATION": "derivation",
    "CHECKERS": "checker_result",
    "REPORT": "report_manifest",
}


class WorkflowError(ValueError):
    """Raised when an artifact skips or tampers with the ESSF workflow."""


def _without_self_hash(artifact: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(artifact)
    workflow = value.get("workflow")
    if isinstance(workflow, dict):
        workflow.pop("artifact_sha256", None)
    return value


def canonical_artifact_hash(artifact: dict[str, Any]) -> str:
    payload = json.dumps(
        _without_self_hash(artifact), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def attach_workflow(
    artifact: dict[str, Any], *, state: str, intent: str,
    predecessor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if state not in STATE_PREDECESSOR:
        raise WorkflowError(f"unknown workflow state {state!r}")
    if intent not in INTENTS:
        raise WorkflowError(f"unknown workflow intent {intent!r}")
    required_predecessor = STATE_PREDECESSOR[state]
    predecessor_meta = None
    history = ["INTENT_CLASSIFY", state]
    if required_predecessor is None:
        if predecessor is not None:
            raise WorkflowError(f"{state} cannot have a predecessor")
    else:
        if predecessor is None:
            raise WorkflowError(f"invalid transition to {state}: predecessor is required")
        try:
            verify_workflow(predecessor, expected_state=required_predecessor)
        except WorkflowError as exc:
            raise WorkflowError(
                f"invalid transition to {state}: expected predecessor state "
                f"{required_predecessor}"
            ) from exc
        previous_workflow = predecessor["workflow"]
        history = list(previous_workflow["history"]) + [state]
        predecessor_meta = {
            "artifact_type": ARTIFACT_TYPES[required_predecessor],
            "state": required_predecessor,
            "sha256": previous_workflow["artifact_sha256"],
        }
    result = copy.deepcopy(artifact)
    result["workflow"] = {
        "version": WORKFLOW_VERSION,
        "intent": intent,
        "state": state,
        "history": history,
        "predecessor": predecessor_meta,
    }
    result["workflow"]["artifact_sha256"] = canonical_artifact_hash(result)
    return result


def verify_workflow(
    artifact: dict[str, Any], *, expected_state: str | None = None,
    predecessor: dict[str, Any] | None = None,
) -> None:
    workflow = artifact.get("workflow") if isinstance(artifact, dict) else None
    if not isinstance(workflow, dict) or workflow.get("version") != WORKFLOW_VERSION:
        raise WorkflowError("v0.4 workflow metadata is required")
    state = workflow.get("state")
    if state not in STATE_PREDECESSOR:
        raise WorkflowError("unknown workflow state")
    if expected_state and state != expected_state:
        raise WorkflowError(f"expected workflow state {expected_state}, got {state}")
    if workflow.get("artifact_sha256") != canonical_artifact_hash(artifact):
        raise WorkflowError("artifact hash mismatch")
    if predecessor is not None:
        verify_workflow(predecessor, expected_state=STATE_PREDECESSOR[state])
        recorded = workflow.get("predecessor") or {}
        if recorded.get("sha256") != predecessor["workflow"]["artifact_sha256"]:
            raise WorkflowError("predecessor hash mismatch")
        if recorded.get("state") != predecessor["workflow"]["state"]:
            raise WorkflowError("predecessor state mismatch")
