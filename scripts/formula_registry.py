#!/usr/bin/env python3
"""Load and bind the machine-readable DF formula registry."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any


REGISTRY_PATH = Path(__file__).resolve().parents[1] / "registries" / "formula_registry.yaml"
PLACEHOLDER = re.compile(r"\{([A-Za-z_]\w*)\}")


class FormulaRegistryError(ValueError):
    """Raised when a formula ID or binding violates the registry contract."""


@lru_cache(maxsize=1)
def load_registry() -> dict[str, Any]:
    try:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FormulaRegistryError(f"Cannot load formula registry: {exc}") from exc
    if registry.get("registry_version") not in {"0.3.1", "0.4"}:
        raise FormulaRegistryError("formula_registry.yaml must declare registry_version=0.3.1 or 0.4")
    if not isinstance(registry.get("models"), dict) or not isinstance(registry.get("formulas"), dict):
        raise FormulaRegistryError("Formula registry requires models and formulas objects.")
    return registry


def model_specs() -> dict[str, dict[str, Any]]:
    return deepcopy(load_registry()["models"])


def get_formula(formula_id: str) -> dict[str, Any]:
    try:
        return deepcopy(load_registry()["formulas"][formula_id])
    except KeyError as exc:
        raise FormulaRegistryError(f"Unknown registered formula: {formula_id}") from exc


def bind_expression(formula_id: str, **bindings: str) -> str:
    expression = get_formula(formula_id)["canonical_sympy_expr"]
    required = set(PLACEHOLDER.findall(expression))
    missing = sorted(required - set(bindings))
    if missing:
        raise FormulaRegistryError(
            f"Formula {formula_id} requires bindings: {', '.join(missing)}"
        )
    for name in required:
        expression = expression.replace("{" + name + "}", str(bindings[name]))
    return expression


def formula_binding(
    formula_id: str,
    expression: str | None = None,
    template_bindings: dict[str, str] | None = None,
) -> dict[str, Any]:
    formula = get_formula(formula_id)
    result = {
        "formula_id": formula_id,
        "source_model_id": formula["source_model_id"],
        "interface": formula["interface"],
        "dimension_signature": formula["dimension_signature"],
        "expression": expression if expression is not None else formula["canonical_sympy_expr"],
    }
    if template_bindings:
        result["template_bindings"] = deepcopy(template_bindings)
    return result
