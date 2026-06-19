#!/usr/bin/env python3
"""Check registered formula metadata and proof-object bindings."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from formula_registry import (
    PLACEHOLDER,
    FormulaRegistryError,
    bind_expression,
    get_formula,
    load_registry,
)


REQUIRED_METADATA = (
    "source_model_id",
    "interface",
    "supported_targets",
    "canonical_sympy_expr",
    "parameters",
    "dimension_signature",
    "numeric_probe_values",
    "source_equation",
    "approximation",
)


def _sympy() -> Any:
    try:
        import sympy
    except Exception as exc:  # pragma: no cover - environment dependent
        raise FormulaRegistryError(f"SymPy is required for formula checking: {exc}") from exc
    return sympy


def _parseable_expression(expression: str) -> str:
    return PLACEHOLDER.sub(lambda match: match.group(1), expression)


def _symbolic_difference(left: str, right: str) -> Any:
    sp = _sympy()
    names = set(re.findall(r"\b[A-Za-z_]\w*\b", left + " " + right)) - {"exp", "pi"}
    local = {name: sp.Symbol(name) for name in names}
    local.update({"exp": sp.exp, "pi": sp.pi})
    return sp.simplify(sp.sympify(left, locals=local) - sp.sympify(right, locals=local))


def check_registry() -> dict[str, Any]:
    errors: list[str] = []
    registry = load_registry()
    for formula_id, formula in registry["formulas"].items():
        missing = [key for key in REQUIRED_METADATA if key not in formula]
        if missing:
            errors.append(f"{formula_id}: missing metadata {', '.join(missing)}")
            continue
        try:
            _symbolic_difference(
                _parseable_expression(formula["canonical_sympy_expr"]),
                _parseable_expression(formula["canonical_sympy_expr"]),
            )
        except Exception as exc:
            errors.append(f"{formula_id}: invalid canonical_sympy_expr: {exc}")
    return {"status": "PASS" if not errors else "FAIL", "errors": errors,
            "checked": len(registry["formulas"])}


def check_binding(binding: dict[str, Any], target: str | None = None) -> list[str]:
    errors: list[str] = []
    formula_id = binding.get("formula_id")
    if not formula_id:
        return ["Formula binding has no formula_id."]
    formula = get_formula(formula_id)
    if binding.get("source_model_id") != formula["source_model_id"]:
        errors.append(f"{formula_id}: source_model_id does not match registry")
    if binding.get("dimension_signature") != formula["dimension_signature"]:
        errors.append(f"{formula_id}: dimension_signature does not match registry")
    if target and target not in formula["supported_targets"]:
        errors.append(f"{formula_id}: target {target} is not registered")
    expression = binding.get("expression")
    canonical = formula["canonical_sympy_expr"]
    expected = canonical
    if PLACEHOLDER.search(canonical):
        template_bindings = binding.get("template_bindings")
        if not isinstance(template_bindings, dict):
            errors.append(f"{formula_id}: template_bindings are required")
            return errors
        try:
            expected = bind_expression(formula_id, **template_bindings)
        except FormulaRegistryError as exc:
            errors.append(str(exc))
            return errors
    if expression:
        try:
            difference = _symbolic_difference(expression, expected)
            if difference != 0:
                errors.append(f"{formula_id}: expression differs from canonical registry formula")
            else:
                sp = _sympy()
                free = sorted(difference.free_symbols, key=str)
                probes = {str(name): value for name, value in formula["numeric_probe_values"].items()}
                substitutions = {
                    symbol: probes.get(str(symbol), 1.25 + index / 10)
                    for index, symbol in enumerate(free)
                }
                numeric = complex(sp.N(difference.subs(substitutions)))
                if abs(numeric) > 1e-9:
                    errors.append(f"{formula_id}: numeric probe differs from registry formula")
        except Exception as exc:
            errors.append(f"{formula_id}: cannot compare expression: {exc}")
    return errors


def check_proof_bindings(proof: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    target = (proof.get("transfer") or {}).get("target_transfer")
    bindings = proof.get("formula_bindings")
    if not isinstance(bindings, list) or not bindings:
        errors.append("proof_object requires non-empty formula_bindings for a registered model")
    else:
        sampled = (proof.get("classification") or {}).get("path") == "SAMPLED_DATA_REGISTERED"
        for binding in bindings:
            try:
                errors.extend(check_binding(binding, None if sampled else target))
            except FormulaRegistryError as exc:
                errors.append(str(exc))
    return {"status": "PASS" if not errors else "FAIL", "errors": errors,
            "checked": len(bindings) if isinstance(bindings, list) else 0}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check formula registry consistency.")
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--all", action="store_true")
    choice.add_argument("--proof")
    args = parser.parse_args()
    try:
        result = check_registry() if args.all else check_proof_bindings(
            json.loads(Path(args.proof).read_text(encoding="utf-8"))
        )
    except (FormulaRegistryError, OSError, json.JSONDecodeError) as exc:
        result = {"status": "FAIL", "errors": [str(exc)], "checked": 0}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
