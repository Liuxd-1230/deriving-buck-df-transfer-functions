#!/usr/bin/env python3
"""Sideband-sum contract helpers for v0.4 sampled-data models."""

from __future__ import annotations

from typing import Any
import re


class SidebandError(ValueError):
    """Raised when a sideband configuration is invalid."""


def _require(spec: dict[str, Any], key: str) -> Any:
    value = spec.get(key)
    if value in (None, ""):
        raise SidebandError(f"sideband {spec.get('mode')} requires {key}")
    return value


def build_sideband(spec: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise SidebandError("sideband spec must be an object")
    mode = spec.get("mode")
    if mode == "SYMBOLIC_FULL_SUM":
        base = str(_require(spec, "base_expression"))
        return {
            "mode": mode,
            "sum_expression": f"sum over n in Z of {base}",
            "numeric_evaluable": False,
            "approximation": "full symbolic infinite sideband sum; not directly numeric",
        }
    if mode == "TRUNCATED_SUM_M":
        base = str(_require(spec, "base_expression"))
        raw_m = _require(spec, "M")
        if isinstance(raw_m, bool) or not isinstance(raw_m, int) or raw_m <= 0:
            raise SidebandError("TRUNCATED_SUM_M requires M to be an explicit positive integer")
        m = raw_m
        import sympy as sp

        n = sp.Symbol("n", integer=True)
        function_names = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", base))
        known_functions = {"exp": sp.exp, "sin": sp.sin, "cos": sp.cos, "sqrt": sp.sqrt}
        identifiers = set(re.findall(r"\b[A-Za-z_]\w*\b", base))
        local: dict[str, Any] = {name: sp.Symbol(name) for name in identifiers - function_names}
        local["n"] = n
        for name in function_names:
            local[name] = known_functions.get(name, sp.Function(name))
        expression = sp.sympify(base, locals=local)
        indices = list(range(-m, 0)) + list(range(1, m + 1))
        terms = [str(expression.subs(n, sp.Integer(index))) for index in indices]
        return {
            "mode": mode,
            "M": m,
            "indices": indices,
            "include_zero": False,
            "sum_expression": f"sum n in [-{m},-1] union [1,{m}] of {base}",
            "numeric_expression": " + ".join(f"({term})" for term in terms),
            "numeric_evaluable": True,
            "approximation": f"truncated nonzero sideband sum M={m}",
        }
    if mode == "PAPER_SIMPLIFIED_FORM":
        expression = str(_require(spec, "expression"))
        return {
            "mode": mode,
            "sum_expression": expression,
            "numeric_expression": expression,
            "numeric_evaluable": True,
            "approximation": "paper simplified sampled-data form",
        }
    raise SidebandError(f"Unsupported sideband mode: {mode!r}")
