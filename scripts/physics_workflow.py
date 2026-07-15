#!/usr/bin/env python3
"""Hash-linked v0.5 physics workflow, isolated from the v0.4 artifact chain."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


WORKFLOW_VERSION = "0.5"
STATE_PREDECESSOR = {
    "IMAGE_INTAKE": None,
    "CIRCUIT_IR_PROPOSED": "IMAGE_INTAKE",
    "TOPOLOGY_CONFIRMED": "CIRCUIT_IR_PROPOSED",
    "PHYSICS_SPEC_CONFIRMED": "TOPOLOGY_CONFIRMED",
    "MODE_DAE": "PHYSICS_SPEC_CONFIRMED",
    "PERIODIC_ORBIT": "MODE_DAE",
    "HYBRID_LINEARIZATION": "PERIODIC_ORBIT",
    "PHYSICS_CHECKERS": "HYBRID_LINEARIZATION",
    "REGISTRY_CROSSCHECK": "PHYSICS_CHECKERS",
    "REPORT": "REGISTRY_CROSSCHECK",
}
ARTIFACT_TYPES = {
    "IMAGE_INTAKE": "image_intake",
    "CIRCUIT_IR_PROPOSED": "circuit_ir_proposed",
    "TOPOLOGY_CONFIRMED": "circuit_ir",
    "PHYSICS_SPEC_CONFIRMED": "physics_spec",
    "MODE_DAE": "mode_dae",
    "PERIODIC_ORBIT": "periodic_orbit",
    "HYBRID_LINEARIZATION": "hybrid_linearization",
    "PHYSICS_CHECKERS": "physics_checker_result",
    "REGISTRY_CROSSCHECK": "registry_crosscheck",
    "REPORT": "physics_report_manifest",
}


class PhysicsWorkflowError(ValueError):
    """Raised when a v0.5 artifact skips or tampers with the workflow."""


def _without_self_hash(value: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(value)
    workflow = result.get("workflow")
    if isinstance(workflow, dict):
        workflow.pop("artifact_sha256", None)
    return result


def canonical_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(
        _without_self_hash(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def content_hash(value: dict[str, Any], *excluded: str) -> str:
    payload = copy.deepcopy(value)
    for key in ("workflow", *excluded):
        payload.pop(key, None)
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def attach_physics_workflow(
    artifact: dict[str, Any], *, state: str, predecessor: dict[str, Any] | None = None
) -> dict[str, Any]:
    if state not in STATE_PREDECESSOR:
        raise PhysicsWorkflowError(f"unknown v0.5 workflow state {state!r}")
    required = STATE_PREDECESSOR[state]
    history = [state]
    predecessor_meta = None
    if required is None:
        if predecessor is not None:
            raise PhysicsWorkflowError(f"{state} cannot have a predecessor")
    else:
        if predecessor is None:
            raise PhysicsWorkflowError(f"{state} requires predecessor {required}")
        verify_physics_workflow(predecessor, expected_state=required)
        previous = predecessor["workflow"]
        history = list(previous["history"]) + [state]
        predecessor_meta = {
            "artifact_type": ARTIFACT_TYPES[required],
            "state": required,
            "sha256": previous["artifact_sha256"],
        }
    result = copy.deepcopy(artifact)
    result["workflow"] = {
        "version": WORKFLOW_VERSION,
        "state": state,
        "history": history,
        "predecessor": predecessor_meta,
    }
    result["workflow"]["artifact_sha256"] = canonical_hash(result)
    return result


def verify_physics_workflow(
    artifact: dict[str, Any], *, expected_state: str | None = None,
    predecessor: dict[str, Any] | None = None,
) -> None:
    workflow = artifact.get("workflow") if isinstance(artifact, dict) else None
    if not isinstance(workflow, dict) or workflow.get("version") != WORKFLOW_VERSION:
        raise PhysicsWorkflowError("v0.5 workflow metadata is required")
    state = workflow.get("state")
    if state not in STATE_PREDECESSOR:
        raise PhysicsWorkflowError("unknown v0.5 workflow state")
    if expected_state and state != expected_state:
        raise PhysicsWorkflowError(f"expected {expected_state}, got {state}")
    if workflow.get("artifact_sha256") != canonical_hash(artifact):
        raise PhysicsWorkflowError("artifact hash mismatch")
    ordered_states = list(STATE_PREDECESSOR)
    expected_history = ordered_states[: ordered_states.index(state) + 1]
    if workflow.get("history") != expected_history:
        raise PhysicsWorkflowError("workflow history is not the exact v0.5 prefix")
    required = STATE_PREDECESSOR[state]
    recorded = workflow.get("predecessor")
    if required is None:
        if recorded is not None:
            raise PhysicsWorkflowError("IMAGE_INTAKE cannot record a predecessor")
    elif not isinstance(recorded, dict):
        raise PhysicsWorkflowError(f"{state} must record predecessor {required}")
    elif recorded.get("state") != required or recorded.get("artifact_type") != ARTIFACT_TYPES[required]:
        raise PhysicsWorkflowError("predecessor state or artifact type mismatch")
    if predecessor is not None:
        verify_physics_workflow(predecessor, expected_state=STATE_PREDECESSOR[state])
        recorded = workflow.get("predecessor") or {}
        if recorded.get("sha256") != predecessor["workflow"]["artifact_sha256"]:
            raise PhysicsWorkflowError("predecessor hash mismatch")
