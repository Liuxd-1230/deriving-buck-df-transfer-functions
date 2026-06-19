#!/usr/bin/env python3
"""Check a v0.4 sampled-data derivation against its proof and registries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from artifact_workflow import WorkflowError, attach_workflow, verify_workflow
from check_formula_consistency import check_binding
from formula_registry import FormulaRegistryError, formula_binding, get_paper_contract
from schema_validation import ArtifactSchemaError, validate_artifact
from sampled_derivation import expand_registered_expressions


def _result(status: str, errors: list[str]) -> dict[str, Any]:
    return {"status": status, "errors": errors}


def check_derivation_artifact(
    derivation: dict[str, Any], proof: dict[str, Any]
) -> dict[str, Any]:
    try:
        validate_artifact(derivation, "derivation.schema.json")
        verify_workflow(derivation, expected_state="DERIVATION", predecessor=proof)
        contract = get_paper_contract(proof["classification"]["model_id"])
    except (ArtifactSchemaError, WorkflowError, FormulaRegistryError, KeyError) as exc:
        return _result("FAIL_DERIVATION_PROVENANCE", [str(exc)])

    expected_order = contract["derivation_order"]
    steps = derivation.get("steps") or []
    if [step.get("object") for step in steps] != expected_order:
        return _result("FAIL_DERIVATION_ORDER", ["derivation steps do not match paper contract"])
    errors: list[str] = []
    expressions = derivation.get("expressions") or {}
    sideband_policy = (derivation.get("approximation_policy") or {}).get("sideband") or {}
    for key in ("mode", "M", "indices", "include_zero", "numeric_approximation"):
        if key in proof.get("sideband", {}) and sideband_policy.get(key) != proof["sideband"].get(key):
            errors.append(f"sideband approximation field {key} differs from proof")
    expanded_expected = expand_registered_expressions(contract)
    if derivation.get("expanded_expressions") != expanded_expected:
        errors.append("expanded expressions do not match the registered derivation chain")
    for object_name, formula_id in contract["formula_objects"].items():
        binding = formula_binding(formula_id)
        binding["expression"] = expressions.get(object_name)
        for error in check_binding(binding, None):
            errors.append(f"{object_name}: {error}")
        matching = [step for step in steps if step.get("object") == object_name]
        if not matching or matching[0].get("formula_id") != formula_id:
            errors.append(f"{object_name}: derivation step formula_id mismatch")
        elif matching[0].get("expression") != expressions.get(object_name):
            errors.append(f"{object_name}: step expression differs from derivation expression")
    target = derivation.get("target_transfer")
    target_object = "GPWM" if target == "Gm" else target
    expected_target_id = contract["formula_objects"].get(target_object)
    if derivation.get("target_formula_id") != expected_target_id:
        errors.append("target formula ID does not match registered target mapping")
    if derivation.get("expanded_target_expression") != expanded_expected.get(target_object):
        errors.append("expanded target expression does not match selected registered target")
    if errors:
        return _result("FAIL_DERIVATION_FORMULA_CONSISTENCY", errors)
    return _result("PASS", [])


def build_checker_artifact(
    derivation: dict[str, Any], proof: dict[str, Any]
) -> dict[str, Any]:
    result = check_derivation_artifact(derivation, proof)
    return attach_workflow(
        {"checker_version": "0.4", **result},
        state="CHECKERS",
        intent=proof["workflow"]["intent"],
        predecessor=derivation,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a v0.4 ESSF derivation artifact.")
    parser.add_argument("--derivation", required=True)
    parser.add_argument("--proof", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()
    try:
        derivation = json.loads(Path(args.derivation).read_text(encoding="utf-8"))
        proof = json.loads(Path(args.proof).read_text(encoding="utf-8"))
        result = build_checker_artifact(derivation, proof)
        if args.out:
            Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, json.JSONDecodeError, WorkflowError, KeyError) as exc:
        result = _result("FAIL_DERIVATION_PROVENANCE", [str(exc)])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
