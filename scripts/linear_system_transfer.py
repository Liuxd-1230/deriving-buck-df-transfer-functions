#!/usr/bin/env python3
"""Generate unverified transfer candidates from typed linear equation systems."""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import sympy as sp

from artifact_workflow import WorkflowError, attach_workflow, verify_workflow
from schema_validation import ArtifactSchemaError, validate_artifact


FUNCTION_NAMES = {"exp", "sin", "cos", "sqrt", "log"}
BLOCK_TYPES = {
    "primitive_equation",
    "open_block",
    "closed_equivalent_block",
    "return_ratio_block",
}
DERIVATION_STEP_REQUIRED = {
    "step_id",
    "title",
    "latex",
    "explanation",
    "source_artifact",
    "latex_origin",
    "provenance",
}


class LinearSystemError(ValueError):
    """Raised when a typed equation system violates the v0.4.5 contract."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def _normalize_expr_text(text: Any) -> str:
    value = str(text or "")

    def replace_function(match: re.Match[str]) -> str:
        name = match.group(1)
        return match.group(0) if name in FUNCTION_NAMES else name

    return re.sub(r"\b([A-Za-z_]\w*)\s*\(\s*s\s*\)", replace_function, value)


def _identifiers(text: Any) -> set[str]:
    return {
        item
        for item in re.findall(r"\b[A-Za-z_]\w*\b", _normalize_expr_text(text))
        if item not in FUNCTION_NAMES and item not in {"I", "pi"}
    }


def _symbol_table(system: dict[str, Any]) -> dict[str, Any]:
    names: set[str] = {"s", "pi"}
    for field in ("symbols", "unknowns", "inputs", "diagnostic_outputs"):
        values = system.get(field) or []
        if isinstance(values, list):
            names.update(str(item) for item in values)
    for group in ("active_equations", "diagnostic_equations"):
        for equation in system.get(group) or []:
            if isinstance(equation, dict):
                names.update(_identifiers(equation.get("lhs")))
                names.update(_identifiers(equation.get("rhs")))
    locals_map: dict[str, Any] = {
        name: sp.Symbol(name)
        for name in names
        if name not in FUNCTION_NAMES and name != "pi"
    }
    locals_map.update({"exp": sp.exp, "sin": sp.sin, "cos": sp.cos, "sqrt": sp.sqrt, "log": sp.log, "pi": sp.pi})
    return locals_map


def _sympify(text: Any, locals_map: dict[str, Any]) -> Any:
    try:
        return sp.sympify(_normalize_expr_text(text), locals=locals_map)
    except Exception as exc:  # pragma: no cover - exact SymPy exception varies by expression
        raise LinearSystemError("FAIL_EXPRESSION_PARSE", f"cannot parse expression {text!r}: {exc}") from exc


def _require_list(system: dict[str, Any], key: str) -> list[str]:
    value = system.get(key)
    if not isinstance(value, list):
        raise LinearSystemError("FAIL_VARIABLE_ROLE_CONFLICT", f"{key} must be a list")
    return [str(item) for item in value]


def _target(system: dict[str, Any]) -> dict[str, Any]:
    target = system.get("target")
    if not isinstance(target, dict):
        raise LinearSystemError("FAIL_TARGET_VARIABLE_NOT_DECLARED", "target must be an object with name/output/input")
    for field in ("name", "output", "input", "response_kind"):
        if target.get(field) in (None, ""):
            raise LinearSystemError("FAIL_TARGET_VARIABLE_NOT_DECLARED", f"target.{field} is required")
    return target


def _blocks(system: dict[str, Any]) -> dict[str, dict[str, Any]]:
    blocks = system.get("blocks") or []
    if not isinstance(blocks, list):
        raise LinearSystemError("FAIL_BLOCK_SHAPE", "blocks must be a list")
    by_id: dict[str, dict[str, Any]] = {}
    for block in blocks:
        if not isinstance(block, dict) or not block.get("id"):
            raise LinearSystemError("FAIL_BLOCK_SHAPE", "each block requires id")
        block_type = block.get("block_type")
        if block_type not in BLOCK_TYPES:
            raise LinearSystemError("FAIL_BLOCK_SHAPE", f"unsupported block_type {block_type!r}")
        if block["id"] in by_id:
            raise LinearSystemError("FAIL_BLOCK_SHAPE", f"duplicate block id {block['id']}")
        by_id[str(block["id"])] = block
    return by_id


def _active_equations(system: dict[str, Any], block_map: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    equations = system.get("active_equations")
    if not isinstance(equations, list) or not equations:
        raise LinearSystemError("FAIL_LINEAR_SYSTEM_EMPTY", "active_equations must be a non-empty list")
    for equation in equations:
        if not isinstance(equation, dict):
            raise LinearSystemError("FAIL_ACTIVE_EQUATION_WITHOUT_BLOCK_ID", "active equation must be an object")
        if not equation.get("block_id"):
            raise LinearSystemError("FAIL_ACTIVE_EQUATION_WITHOUT_BLOCK_ID", f"{equation.get('id', '<unknown>')} lacks block_id")
        if str(equation["block_id"]) not in block_map:
            raise LinearSystemError("FAIL_ACTIVE_EQUATION_WITHOUT_BLOCK_ID", f"{equation['block_id']} is not a declared block")
        if equation.get("role") != "active":
            raise LinearSystemError("FAIL_ACTIVE_EQUATION_WITHOUT_BLOCK_ID", f"{equation.get('id')} must have role=active")
        for field in ("id", "lhs", "rhs"):
            if equation.get(field) in (None, ""):
                raise LinearSystemError("FAIL_ACTIVE_EQUATION_WITHOUT_BLOCK_ID", f"active equation missing {field}")
    return equations


def _diagnostic_equations(system: dict[str, Any]) -> list[dict[str, Any]]:
    equations = system.get("diagnostic_equations", [])
    if not isinstance(equations, list):
        raise LinearSystemError("FAIL_BLOCK_SHAPE", "diagnostic_equations must be a list")
    return [equation for equation in equations if isinstance(equation, dict)]


def _eliminated_variables(block_map: dict[str, dict[str, Any]]) -> set[str]:
    variables: set[str] = set()
    for block in block_map.values():
        for name in block.get("eliminated_variables") or []:
            variables.add(str(name))
    return variables


def _validate_variable_roles(system: dict[str, Any], eliminated: set[str]) -> tuple[list[str], list[str], dict[str, Any]]:
    unknowns = _require_list(system, "unknowns")
    inputs = _require_list(system, "inputs")
    target = _target(system)
    if set(unknowns) & set(inputs):
        raise LinearSystemError("FAIL_VARIABLE_ROLE_CONFLICT", "unknowns and inputs must be disjoint")
    if target["output"] not in unknowns or target["input"] not in inputs:
        raise LinearSystemError("FAIL_TARGET_VARIABLE_NOT_DECLARED", "target output/input must be declared in unknowns/inputs")
    if eliminated & set(unknowns) or target["output"] in eliminated or target["input"] in eliminated:
        raise LinearSystemError(
            "FAIL_REINTRODUCED_ELIMINATED_INTERNAL_VARIABLE",
            "eliminated variables cannot be active unknowns or target variables",
        )
    return unknowns, inputs, target


def _validate_eliminated_not_active(
    active_equations: list[dict[str, Any]], eliminated: set[str]
) -> None:
    if not eliminated:
        return
    for equation in active_equations:
        used = _identifiers(equation.get("lhs")) | _identifiers(equation.get("rhs"))
        repeated = sorted(used & eliminated)
        if repeated:
            raise LinearSystemError(
                "FAIL_REINTRODUCED_ELIMINATED_INTERNAL_VARIABLE",
                f"{equation.get('id')} reintroduces eliminated variables: {', '.join(repeated)}",
            )


def _validate_block_shapes(
    system: dict[str, Any],
    block_map: dict[str, dict[str, Any]],
    active_equations: list[dict[str, Any]],
) -> None:
    equations_by_block: dict[str, list[dict[str, Any]]] = {}
    for equation in active_equations:
        equations_by_block.setdefault(str(equation["block_id"]), []).append(equation)
    signal_vars = set(_require_list(system, "unknowns")) | set(_require_list(system, "inputs"))
    signal_vars.update(str(item) for item in system.get("diagnostic_outputs") or [])
    for block_id, block in block_map.items():
        block_type = block["block_type"]
        if block_type == "open_block" and block.get("feedback_paths_already_closed"):
            raise LinearSystemError("FAIL_BLOCK_SHAPE", f"{block_id} is open but declares closed feedback paths")
        if block_type == "return_ratio_block":
            loop_break = block.get("loop_break")
            if not isinstance(loop_break, dict) or not loop_break.get("injection") or not loop_break.get("return"):
                raise LinearSystemError("FAIL_RETURN_RATIO_LOOP_BREAK_REQUIRED", f"{block_id} lacks loop_break injection/return")
        if block_type != "closed_equivalent_block":
            continue
        for field in ("eliminated_variables", "eliminated_equations", "feedback_paths_already_closed"):
            if not block.get(field):
                raise LinearSystemError("FAIL_BLOCK_SHAPE", f"{block_id} missing {field}")
        block_equations = equations_by_block.get(block_id, [])
        if len(block_equations) != 1:
            raise LinearSystemError("FAIL_BLOCK_SHAPE", f"{block_id} must bind exactly one active equation in v0.4.5")
        equation = block_equations[0]
        rhs_signals = sorted((_identifiers(equation["rhs"]) & signal_vars) - {str(equation["lhs"])})
        if len(rhs_signals) > 1:
            raise LinearSystemError(
                "FAIL_MIMO_CLOSED_EQUIVALENT_NOT_SUPPORTED_V045",
                f"{block_id} uses multiple input signals: {', '.join(rhs_signals)}",
            )
        if len(rhs_signals) != 1:
            raise LinearSystemError("FAIL_BLOCK_SHAPE", f"{block_id} must be SISO y=K(s)*x")
        if block.get("input") and str(block["input"]) != rhs_signals[0]:
            raise LinearSystemError("FAIL_BLOCK_SHAPE", f"{block_id} input does not match active equation")


def _validate_linearity(equations: list[Any], unknown_symbols: list[Any]) -> None:
    try:
        for expression in equations:
            poly = sp.Poly(expression, *unknown_symbols)
            if poly.total_degree() > 1:
                raise LinearSystemError("FAIL_NONLINEAR_IN_UNKNOWNS", "active equations must be linear in unknowns")
        sp.linear_eq_to_matrix(equations, unknown_symbols)
    except LinearSystemError:
        raise
    except Exception as exc:
        raise LinearSystemError("FAIL_NONLINEAR_IN_UNKNOWNS", str(exc)) from exc


def _active_symbolic_equations(
    active_equations: list[dict[str, Any]], locals_map: dict[str, Any]
) -> list[Any]:
    symbolic = []
    for equation in active_equations:
        lhs = _sympify(equation["lhs"], locals_map)
        rhs = _sympify(equation["rhs"], locals_map)
        symbolic.append(lhs - rhs)
    return symbolic


def _solve_transfer(
    symbolic_equations: list[Any],
    *,
    unknowns: list[str],
    inputs: list[str],
    target: dict[str, Any],
    locals_map: dict[str, Any],
) -> Any:
    unknown_symbols = [locals_map[name] for name in unknowns]
    input_symbol = locals_map[target["input"]]
    output_symbol = locals_map[target["output"]]
    _validate_linearity(symbolic_equations, unknown_symbols)
    try:
        solutions = sp.solve(symbolic_equations, unknown_symbols, dict=True, simplify=False)
    except Exception as exc:
        raise LinearSystemError("FAIL_LINEAR_SOLVE", str(exc)) from exc
    if not solutions or output_symbol not in solutions[0]:
        raise LinearSystemError("FAIL_LINEAR_SOLVE", "solver did not produce the target output")
    expression = solutions[0][output_symbol]
    substitutions = {
        locals_map[name]: 0
        for name in inputs
        if name != target["input"]
    }
    expression = expression.subs(substitutions)
    transfer = sp.factor(sp.simplify(expression / input_symbol))
    if input_symbol in transfer.free_symbols:
        raise LinearSystemError("FAIL_LINEAR_SOLVE", "target input remains in generated transfer")
    return transfer


def _source_equations_for_denominator(
    active_equations: list[dict[str, Any]], block_map: dict[str, dict[str, Any]]
) -> tuple[list[str], str]:
    source_ids = [str(equation["id"]) for equation in active_equations]
    feedback_candidates: list[str] = []
    for equation in active_equations:
        block = block_map[str(equation["block_id"])]
        if block.get("feedback_path"):
            feedback_candidates.append(str(block["feedback_path"]))
        elif "sense" in str(block.get("id", "")).lower():
            feedback_candidates.append(str(block["id"]))
        for path in block.get("feedback_paths_already_closed") or []:
            feedback_candidates.append(str(path))
    return source_ids, (feedback_candidates[0] if feedback_candidates else "active_equation_feedback")


def _denominator_provenance(
    transfer: Any,
    active_equations: list[dict[str, Any]],
    block_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    _, denominator = sp.fraction(sp.factor(transfer))
    if sp.simplify(denominator - 1) == 0:
        return []
    source_ids, feedback_path = _source_equations_for_denominator(active_equations, block_map)
    return [{
        "factor_or_term": str(denominator),
        "source_equations": source_ids,
        "feedback_path": feedback_path,
        "generated_by_solver": True,
    }]


def _latex_equation(lhs: Any, rhs: Any) -> str:
    return f"{sp.latex(lhs)}={sp.latex(rhs)}"


def _target_latex(target: dict[str, Any], locals_map: dict[str, Any]) -> str:
    return (
        f"{target['name']}(s)="
        + r"\frac{"
        + sp.latex(locals_map[target["output"]])
        + "}{"
        + sp.latex(locals_map[target["input"]])
        + "}"
    )


def _derivation_steps(
    system: dict[str, Any],
    *,
    active_equations: list[dict[str, Any]],
    diagnostic_equations: list[dict[str, Any]],
    transfer: Any,
    target: dict[str, Any],
    locals_map: dict[str, Any],
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = [{
        "step_id": "target_definition",
        "title": "目标传函",
        "latex": _target_latex(target, locals_map),
        "explanation": "目标传函由 target.output 与 target.input 字段定义，报告不手写目标比值。",
        "source_artifact": "linear_equation_system.json",
        "latex_origin": "solver_generated",
        "provenance": "target.output/input",
    }]
    for equation in active_equations:
        lhs = _sympify(equation["lhs"], locals_map)
        rhs = _sympify(equation["rhs"], locals_map)
        steps.append({
            "step_id": str(equation["id"]),
            "title": f"active 方程 {equation['id']}",
            "latex": _latex_equation(lhs, rhs),
            "explanation": f"该 active equation 绑定 block `{equation['block_id']}`，并进入矩阵消元。",
            "source_artifact": "linear_equation_system.json",
            "latex_origin": "user_supplied_diagnostic",
            "provenance": f"block_id={equation['block_id']}",
        })
    for equation in diagnostic_equations:
        if equation.get("lhs") and equation.get("rhs"):
            lhs = _sympify(equation["lhs"], locals_map)
            rhs = _sympify(equation["rhs"], locals_map)
            latex = _latex_equation(lhs, rhs)
        else:
            latex = str(equation.get("note", equation.get("id", "diagnostic")))
        steps.append({
            "step_id": str(equation.get("id", "diagnostic")),
            "title": f"diagnostic 方程 {equation.get('id', 'diagnostic')}",
            "latex": latex,
            "explanation": "该 diagnostic equation 仅用于报告、sanity check 或 provenance notes，不进入传函消元。",
            "source_artifact": "linear_equation_system.json",
            "latex_origin": "user_supplied_diagnostic",
            "provenance": "diagnostic_equations",
        })
    steps.append({
        "step_id": "solver_generated_transfer",
        "title": "求解器生成候选传函",
        "latex": f"{target['name']}(s)={sp.latex(transfer)}",
        "explanation": "候选传函由 linear_system_transfer.py 对 active_equations 统一消元生成。",
        "source_artifact": "derivation.json",
        "latex_origin": "solver_generated",
        "provenance": "linear_system_transfer.py",
    })
    return steps


def validate_derivation_steps(steps: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for index, step in enumerate(steps):
        missing = sorted(DERIVATION_STEP_REQUIRED - set(step))
        if missing:
            errors.append(f"derivation_steps[{index}] missing {', '.join(missing)}")
        if step.get("latex_origin") not in {"solver_generated", "registry_binding", "user_supplied_diagnostic"}:
            errors.append(f"derivation_steps[{index}] has invalid latex_origin")
        if step.get("source_artifact") not in {
            "linear_equation_system.json",
            "derivation.json",
            "formula_registry.yaml",
        }:
            errors.append(f"derivation_steps[{index}] has invalid source_artifact")
    return errors


def derive_linear_system_transfer(
    system: dict[str, Any],
    *,
    proof: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a derivation artifact whose candidate expression is solver-generated."""

    if not isinstance(system, dict):
        raise LinearSystemError("FAIL_LINEAR_SYSTEM_EMPTY", "linear equation system must be an object")
    if system.get("transfer_function") or system.get("candidate_transfer_expression"):
        raise LinearSystemError(
            "FAIL_HAND_WRITTEN_DENOMINATOR_IN_UNVERIFIED_PATH",
            "unverified paths cannot submit hand-written transfer expressions",
        )
    validate_artifact(system, "linear_equation_system.schema.json")
    block_map = _blocks(system)
    active = _active_equations(system, block_map)
    diagnostic = _diagnostic_equations(system)
    eliminated = _eliminated_variables(block_map)
    unknowns, inputs, target = _validate_variable_roles(system, eliminated)
    _validate_eliminated_not_active(active, eliminated)
    _validate_block_shapes(system, block_map, active)
    locals_map = _symbol_table(system)
    symbolic_equations = _active_symbolic_equations(active, locals_map)
    transfer = _solve_transfer(
        symbolic_equations,
        unknowns=unknowns,
        inputs=inputs,
        target=target,
        locals_map=locals_map,
    )
    denominator_provenance = _denominator_provenance(transfer, active, block_map)
    steps = _derivation_steps(
        system,
        active_equations=active,
        diagnostic_equations=diagnostic,
        transfer=transfer,
        target=target,
        locals_map=locals_map,
    )
    step_errors = validate_derivation_steps(steps)
    if step_errors:
        raise LinearSystemError("FAIL_DERIVATION_STEPS_SCHEMA", "; ".join(step_errors))
    eliminated_for_solution = [name for name in unknowns if name != target["output"]]
    validation_level = "PROTOCOL_DERIVED_UNVERIFIED"
    classification = {"path": "PROTOCOL_DERIVED_NEW", "model_id": None}
    if proof:
        validation = proof.get("validation") if isinstance(proof.get("validation"), dict) else {}
        validation_level = validation.get("level", validation_level)
        classification = deepcopy(proof.get("classification") or classification)
    artifact = {
        "derivation_version": "0.4.5",
        "case_id": system.get("case_id") or (proof or {}).get("case_id", "linear-system-case"),
        "classification": classification,
        "target_transfer": target["name"],
        "response_kind": target["response_kind"],
        "target": deepcopy(target),
        "linear_equation_system": deepcopy(system),
        "generated_by": "linear_system_transfer.py",
        "generated_expression": str(transfer),
        "expanded_target_expression": str(transfer),
        "expressions": {target["name"]: str(transfer)},
        "reasoning_method": {
            "name": "v0.4.5 typed linear equation system",
            "active_equations_only": True,
            "candidate_transfer_source": "linear_system_transfer.py",
        },
        "steps": [
            {
                "index": index,
                "object": step["step_id"],
                "formula_id": None,
                "expression": step["latex"],
                "source_equation": step["source_artifact"],
                "approximation": "protocol-derived",
                "dimension_signature": "not-checked",
            }
            for index, step in enumerate(steps, start=1)
        ],
        "derivation_steps": steps,
        "elimination_metadata": {
            "active_equations": [equation["id"] for equation in active],
            "diagnostic_equations": [equation.get("id") for equation in diagnostic],
            "eliminated_variables": eliminated_for_solution,
            "block_trace": [
                {
                    "equation": equation["id"],
                    "block_id": equation["block_id"],
                    "block_type": block_map[str(equation["block_id"])]["block_type"],
                    "eliminated_variables": block_map[str(equation["block_id"])].get("eliminated_variables", []),
                    "feedback_paths": block_map[str(equation["block_id"])].get("feedback_paths_already_closed", []),
                }
                for equation in active
            ],
        },
        "denominator_provenance": denominator_provenance,
        "approximation_policy": deepcopy(
            system.get("approximation_policy")
            or {"declared": False, "items": [], "valid_frequency": "not_declared"}
        ),
        "validation": {
            "level": validation_level,
            "completed": ["linear-system-solver-generation"],
            "missing": ["paper-benchmark", "switching-simulation"],
        },
    }
    if proof is not None:
        verify_workflow(proof, expected_state="FORMULA_BINDING")
        artifact = attach_workflow(
            artifact,
            state="DERIVATION",
            intent=proof["workflow"]["intent"],
            predecessor=proof,
        )
    validate_artifact(artifact, "derivation.schema.json")
    return artifact


def derive_linear_system_from_proof(proof: dict[str, Any]) -> dict[str, Any]:
    classification = proof.get("classification") or {}
    if classification.get("path") != "PROTOCOL_DERIVED_NEW":
        raise LinearSystemError("FAIL_LINEAR_SYSTEM_PATH", "linear system derivation requires PROTOCOL_DERIVED_NEW")
    system = proof.get("linear_equation_system")
    if not isinstance(system, dict):
        raise LinearSystemError("FAIL_LINEAR_SYSTEM_EMPTY", "proof object lacks linear_equation_system")
    transfer = proof.get("transfer") if isinstance(proof.get("transfer"), dict) else {}
    if transfer.get("origin") != "linear-system-pending":
        raise LinearSystemError("FAIL_HAND_WRITTEN_DENOMINATOR_IN_UNVERIFIED_PATH", "proof transfer is not solver-pending")
    if transfer.get("expression") not in (None, "", "linear-system-pending"):
        raise LinearSystemError(
            "FAIL_HAND_WRITTEN_DENOMINATOR_IN_UNVERIFIED_PATH",
            "proof carries a hand-written transfer expression",
        )
    return derive_linear_system_transfer(system, proof=proof)


def main() -> int:
    parser = argparse.ArgumentParser(description="Derive a transfer from a typed linear equation system.")
    parser.add_argument("--system")
    parser.add_argument("--proof")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        if args.proof:
            proof = json.loads(Path(args.proof).read_text(encoding="utf-8"))
            derivation = derive_linear_system_from_proof(proof)
        else:
            if not args.system:
                raise LinearSystemError("FAIL_LINEAR_SYSTEM_EMPTY", "--system or --proof is required")
            system = json.loads(Path(args.system).read_text(encoding="utf-8"))
            derivation = derive_linear_system_transfer(system)
        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(derivation, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote linear-system derivation artifact: {output.resolve()}")
        return 0
    except (
        OSError,
        json.JSONDecodeError,
        LinearSystemError,
        ArtifactSchemaError,
        WorkflowError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
