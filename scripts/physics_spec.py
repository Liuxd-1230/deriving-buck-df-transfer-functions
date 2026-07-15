#!/usr/bin/env python3
"""Second user-confirmation boundary for the v0.5 physics specification."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from hybrid_mna import physics_spec_content_hash, validate_physics_spec
from physics_workflow import attach_physics_workflow, verify_physics_workflow


def confirm_physics_spec(raw_spec: dict[str, Any], circuit_ir: dict[str, Any]) -> dict[str, Any]:
    verify_physics_workflow(circuit_ir, expected_state="TOPOLOGY_CONFIRMED")
    spec = copy.deepcopy(raw_spec)
    spec.pop("workflow", None)
    spec["spec_version"] = "0.5"
    spec["status"] = "PHYSICS_SPEC_CONFIRMED"
    spec["case_id"] = circuit_ir["case_id"]
    spec["circuit_ir_sha256"] = circuit_ir["workflow"]["artifact_sha256"]
    sequence = spec.get("mode_sequence") or []
    if "poincare_section" not in spec and sequence:
        spec["poincare_section"] = {
            "mode": sequence[0]["mode"],
            "position": "immediately_after_transition",
            "definition": "period_start_after_turn_on",
        }
    elif "poincare_section" in spec:
        spec["poincare_section"].setdefault("definition", "period_start_after_turn_on")
    spec["confirmation"] = {
        "confirmed_by": "user",
        "confirmed_content_sha256": "0" * 64,
    }
    spec["confirmation"]["confirmed_content_sha256"] = physics_spec_content_hash(spec)
    spec = attach_physics_workflow(spec, state="PHYSICS_SPEC_CONFIRMED", predecessor=circuit_ir)
    validate_physics_spec(spec, circuit_ir)
    return spec


def main() -> int:
    parser = argparse.ArgumentParser(description="Confirm or validate a v0.5 physics spec.")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--circuit-ir", required=True)
    parser.add_argument("--out")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    try:
        raw = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        circuit = json.loads(Path(args.circuit_ir).read_text(encoding="utf-8"))
        if args.validate_only:
            validate_physics_spec(raw, circuit)
            result = raw
        else:
            if not args.out:
                raise ValueError("--out is required unless --validate-only is used")
            result = confirm_physics_spec(raw, circuit)
            Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("PASS")
        return 0
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
