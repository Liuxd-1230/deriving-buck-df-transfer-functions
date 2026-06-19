#!/usr/bin/env python3
"""Sideband-sum contract helpers for v0.4 sampled-data models."""

from __future__ import annotations

from typing import Any


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
        m = int(_require(spec, "M"))
        terms = [base.replace("n", f"({index})") for index in range(-m, m + 1)]
        return {
            "mode": mode,
            "M": m,
            "sum_expression": f"sum n=-{m}..{m} of {base}",
            "numeric_expression": " + ".join(f"({term})" for term in terms),
            "numeric_evaluable": True,
            "approximation": f"truncated sideband sum n=-{m}..{m}",
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
