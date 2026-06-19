#!/usr/bin/env python3
"""Validate the minimum ESSF v0.3.1 proof-object contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from check_formula_consistency import check_binding, check_proof_bindings
from formula_registry import FormulaRegistryError, load_registry


REGISTERED_PATHS = {"DF_REGISTERED_DIRECT", "DF_REGISTERED_MULTIPORT"}
A_STAR_KEYS = {"a_c", "a_g", "a_o", "a_i"}


def _result(status: str, errors: list[str]) -> dict[str, Any]:
    return {"status": status, "errors": errors}


def _contains_a_star_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(key in A_STAR_KEYS or _contains_a_star_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_a_star_key(item) for item in value)
    return False


def check_proof_object(proof: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(proof, dict) or proof.get("proof_version") != "0.3.1":
        return _result("FAIL_NOT_PROOF_OBJECT", ["proof_version=0.3.1 is required"])
    intake = proof.get("intake") or {}
    if intake.get("status") != "COMPLETE":
        return _result("FAIL_INCOMPLETE_INTAKE", ["intake status must be COMPLETE"])
    classification = proof.get("classification") or {}
    path = classification.get("path")
    if path not in REGISTERED_PATHS | {"PROTOCOL_DERIVED_NEW"}:
        return _result("FAIL_MISSING_CLASSIFICATION", ["recognized classification.path is required"])

    model_id = classification.get("model_id")
    transfer = proof.get("transfer") or {}
    target = transfer.get("target_transfer")
    modulator = proof.get("modulator") or {}
    registry = load_registry()

    if path in REGISTERED_PATHS:
        if model_id not in registry["models"]:
            return _result("FAIL_FORMULA_CONSISTENCY", ["registered path requires registry model_id"])
        model = registry["models"][model_id]
        if target not in model["supported_targets"]:
            return _result("FAIL_REGISTERED_TARGET", [f"{target} is not registered for {model_id}"])
        expected_interface = "direct-transfer" if path == "DF_REGISTERED_DIRECT" else "a-star"
        if model["interface"] != expected_interface or modulator.get("model_type") != expected_interface:
            return _result("FAIL_INTERFACE_MISMATCH", ["classification, registry, and modulator interface differ"])
        if path == "DF_REGISTERED_DIRECT" and _contains_a_star_key(proof):
            return _result("FAIL_DIRECT_MODEL_FAKE_A_STAR", ["direct-transfer proof contains a_* coefficients"])
        formula_result = check_proof_bindings(proof)
        if formula_result["status"] != "PASS":
            return _result("FAIL_FORMULA_CONSISTENCY", formula_result["errors"])
        binding_ids = {item.get("formula_id") for item in proof.get("formula_bindings", [])}
        if path == "DF_REGISTERED_DIRECT":
            if transfer.get("formula_id") not in binding_ids:
                return _result("FAIL_FORMULA_CONSISTENCY", ["direct transfer formula is not bound"])
            transfer_binding = next(
                item for item in proof["formula_bindings"]
                if item.get("formula_id") == transfer.get("formula_id")
            )
            transfer_check = dict(transfer_binding)
            transfer_check["expression"] = transfer.get("expression")
            transfer_errors = check_binding(transfer_check, target)
            if transfer_errors:
                return _result("FAIL_FORMULA_CONSISTENCY", transfer_errors)
            wrong_sources = [
                item.get("formula_id") for item in proof.get("formula_bindings", [])
                if item.get("source_model_id") != model_id
                or registry["formulas"].get(item.get("formula_id"), {}).get("interface") != "direct-transfer"
            ]
            if wrong_sources:
                return _result("FAIL_FORMULA_CONSISTENCY", [
                    "direct proof binds formulas from another model: " + ", ".join(wrong_sources)
                ])
        if path == "DF_REGISTERED_MULTIPORT":
            coefficients = modulator.get("coefficients")
            if not isinstance(coefficients, dict) or set(coefficients) != A_STAR_KEYS:
                return _result("FAIL_MULTIPORT_BINDING", ["a-star proof requires four coefficient bindings"])
            if any(item.get("formula_id") not in binding_ids for item in coefficients.values()):
                return _result("FAIL_MULTIPORT_BINDING", ["every a_* coefficient must bind the registry"])
            allowed_sources = {model_id, "common-current-source-adapter", "common-zero-path"}
            for item in coefficients.values():
                formula = registry["formulas"].get(item["formula_id"], {})
                if formula.get("interface") != "a-star" or formula.get("source_model_id") not in allowed_sources:
                    return _result("FAIL_MULTIPORT_BINDING", [
                        f"{item['formula_id']} is not an allowed a-star formula for {model_id}"
                    ])
            if transfer.get("origin") != "registered-buck-sympy-elimination" or not transfer.get("expression"):
                return _result("FAIL_MULTIPORT_BINDING", [
                    "registered multiport transfer must come from Buck SymPy elimination"
                ])

    validation = proof.get("validation") or {}
    expected_level = (
        "PROTOCOL_DERIVED_UNVERIFIED" if path == "PROTOCOL_DERIVED_NEW"
        else "PAPER_GROUNDED_PARTIAL"
    )
    if validation.get("level") != expected_level:
        return _result("FAIL_VALIDATION_LEVEL", [f"{path} requires {expected_level}"])
    return _result("PASS", [])


def main() -> int:
    parser = argparse.ArgumentParser(description="Check an ESSF v0.3.1 proof object.")
    parser.add_argument("--proof", required=True)
    args = parser.parse_args()
    try:
        proof = json.loads(Path(args.proof).read_text(encoding="utf-8"))
        result = check_proof_object(proof)
    except (OSError, json.JSONDecodeError, FormulaRegistryError) as exc:
        result = _result("FAIL_NOT_PROOF_OBJECT", [str(exc)])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
