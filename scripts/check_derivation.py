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
from linear_system_transfer import LinearSystemError, derive_linear_system_from_proof, validate_derivation_steps
from schema_validation import ArtifactSchemaError, validate_artifact
from sampled_derivation import expand_registered_expressions, numeric_sideband_overrides
from run_validation_checks import build_unified_checker_result


def _result(status: str, errors: list[str]) -> dict[str, Any]:
    return {"status": status, "errors": errors}


def _sideband_placeholder(contract: dict[str, Any]) -> str | None:
    formula_id = (contract.get("formula_objects") or {}).get("sideband")
    if not formula_id:
        return None
    from formula_registry import get_formula

    formula = get_formula(formula_id)
    expression = str(formula.get("canonical_sympy_expr", ""))
    if expression in {"SidebandPulse", "SumG"}:
        return expression
    return None


def check_derivation_artifact(
    derivation: dict[str, Any], proof: dict[str, Any]
) -> dict[str, Any]:
    if derivation.get("derivation_version") == "0.4.5" or (proof.get("classification") or {}).get("path") == "PROTOCOL_DERIVED_NEW":
        return check_linear_derivation_artifact(derivation, proof)
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
    numeric_expanded = derivation.get("numeric_expanded_expressions")
    numeric_target = derivation.get("numeric_expanded_target_expression")
    placeholder = _sideband_placeholder(contract)
    sideband_mode = sideband_policy.get("mode")
    if sideband_mode in {"TRUNCATED_SUM_M", "PAPER_SIMPLIFIED_FORM"}:
        if not isinstance(numeric_expanded, dict) or not numeric_target:
            errors.append("numeric sideband approximation requires numeric expanded expressions")
        expected_numeric = expand_registered_expressions(
            contract,
            object_overrides=numeric_sideband_overrides(proof),
            simplify=False,
        )
        if numeric_expanded != expected_numeric:
            errors.append("numeric expanded expressions do not match proof sideband approximation")
        if numeric_target != expected_numeric.get(derivation.get("target_transfer")):
            target_object_for_numeric = "GPWM" if derivation.get("target_transfer") == "Gm" else derivation.get("target_transfer")
            if numeric_target != expected_numeric.get(target_object_for_numeric):
                errors.append("numeric expanded target expression does not match proof sideband approximation")
        if placeholder and placeholder in str(numeric_target):
            errors.append(
                f"numeric expanded target still contains sideband placeholder {placeholder}"
            )
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


def check_linear_derivation_artifact(
    derivation: dict[str, Any], proof: dict[str, Any]
) -> dict[str, Any]:
    try:
        validate_artifact(derivation, "derivation.schema.json")
        verify_workflow(derivation, expected_state="DERIVATION", predecessor=proof)
    except (ArtifactSchemaError, WorkflowError) as exc:
        return _result("FAIL_LINEAR_EQUATION_SYSTEM_CHECK", [str(exc)])
    errors: list[str] = []
    transfer = proof.get("transfer") if isinstance(proof.get("transfer"), dict) else {}
    if transfer.get("origin") != "linear-system-pending":
        errors.append("proof transfer is not linear-system-pending")
    if transfer.get("expression") not in (None, "", "linear-system-pending"):
        errors.append("proof contains a hand-written transfer expression")
    if derivation.get("generated_by") != "linear_system_transfer.py":
        errors.append("candidate transfer expression was not generated by linear_system_transfer.py")
    denominator = derivation.get("denominator_provenance")
    if denominator is None:
        errors.append("denominator_provenance is missing")
    elif any(not item.get("generated_by_solver") for item in denominator if isinstance(item, dict)):
        errors.append("denominator_provenance contains non-solver-generated terms")
    step_errors = validate_derivation_steps(derivation.get("derivation_steps") or [])
    errors.extend(step_errors)
    try:
        expected = derive_linear_system_from_proof(proof)
        for field in ("generated_expression", "expanded_target_expression", "denominator_provenance"):
            if derivation.get(field) != expected.get(field):
                errors.append(f"{field} differs from re-generated linear system derivation")
        if derivation.get("derivation_steps") != expected.get("derivation_steps"):
            errors.append("derivation_steps differ from re-generated linear system derivation")
    except (LinearSystemError, ArtifactSchemaError, WorkflowError) as exc:
        errors.append(str(exc))
    if errors:
        return _result("FAIL_LINEAR_EQUATION_SYSTEM_CHECK", errors)
    return _result("PASS", [])


def build_checker_artifact(
    derivation: dict[str, Any], proof: dict[str, Any]
) -> dict[str, Any]:
    result = check_derivation_artifact(derivation, proof)
    intake = proof.get("intake", {})
    normalized = intake.get("normalized") if isinstance(intake, dict) else {}
    classification = proof.get("classification", {})
    unified = build_unified_checker_result(
        intake={"status": intake.get("status", "COMPLETE"), "normalized": normalized},
        classification=classification
        | {"validation_level": (proof.get("validation") or {}).get("level")},
        proof=proof,
        derivation=derivation,
        derivation_check=result,
    )
    return attach_workflow(
        {"checker_version": "0.4.5", **result, **unified},
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
