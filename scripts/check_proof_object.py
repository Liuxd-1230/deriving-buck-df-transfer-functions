#!/usr/bin/env python3
"""Validate the minimum ESSF v0.3.1 proof-object contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from check_formula_consistency import check_binding, check_proof_bindings
from formula_registry import FormulaRegistryError, get_formula, get_paper_contract, load_registry
from artifact_workflow import WorkflowError, verify_workflow
from schema_validation import ArtifactSchemaError, validate_artifact


REGISTERED_PATHS = {"DF_REGISTERED_DIRECT", "DF_REGISTERED_MULTIPORT"}
SAMPLED_DATA_PATH = "SAMPLED_DATA_REGISTERED"
SAMPLED_PART_FAMILIES = {
    "SAMPLED_DATA_REGISTERED_PART_I_PCM_VCM_PVM_VVM",
    "SAMPLED_DATA_REGISTERED_PART_II_CCOT_CCOFT",
    "SAMPLED_DATA_REGISTERED_PART_II_VCOT_VCOFT",
}
A_STAR_KEYS = {"a_c", "a_g", "a_o", "a_i"}


def _result(status: str, errors: list[str]) -> dict[str, Any]:
    return {"status": status, "errors": errors}


def _contains_a_star_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(key in A_STAR_KEYS or _contains_a_star_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_a_star_key(item) for item in value)
    return False


def _check_sampled_data_contract(proof: dict[str, Any]) -> dict[str, Any] | None:
    classification = proof.get("classification") or {}
    if classification.get("part_family") not in SAMPLED_PART_FAMILIES:
        return _result("FAIL_SAMPLED_DATA_PART_FAMILY", ["sampled-data proof requires a recognized part_family"])

    sampling = proof.get("sampling")
    required_sampling = {
        "sampling_instant",
        "sampled_variable",
        "left_limit",
        "right_limit",
        "dirichlet_value",
        "dirichlet_required",
    }
    if not isinstance(sampling, dict) or any(sampling.get(key) in (None, "") for key in required_sampling):
        return _result("FAIL_DIRICHLET_INCOMPLETE", ["sampling must include left/right limits and Dirichlet value"])

    fm = proof.get("Fm")
    if not isinstance(fm, dict) or not fm.get("expression") or not fm.get("type"):
        return _result("FAIL_FM_INCOMPLETE", ["sampled-data proof requires Fm type and expression"])
    if fm.get("origin") == "sampled_data_derivation":
        steps = " ".join(str(item) for item in fm.get("derivation_steps", []))
        reference = str(fm.get("dirichlet_reference", ""))
        if "dirichlet" not in (reference + " " + steps).lower():
            return _result("FAIL_FM_WITHOUT_DIRICHLET_REFERENCE", [
                "Fm derived by sampled-data method must reference sampling.dirichlet_value"
            ])

    sideband = proof.get("sideband")
    if not isinstance(sideband, dict) or sideband.get("mode") not in {
        "SYMBOLIC_FULL_SUM",
        "TRUNCATED_SUM_M",
        "PAPER_SIMPLIFIED_FORM",
    }:
        return _result("FAIL_SIDEBAND_MODE_MISSING", ["sampled-data proof requires explicit sideband mode"])

    part_family = classification.get("part_family")
    if part_family in {
        "SAMPLED_DATA_REGISTERED_PART_II_CCOT_CCOFT",
        "SAMPLED_DATA_REGISTERED_PART_II_VCOT_VCOFT",
    }:
        pulse = proof.get("pulse_structure")
        factor_text = ""
        if isinstance(pulse, dict):
            factor_text = " ".join(str(pulse.get(key, "")) for key in ("frequency_factor", "relation", "d1", "d2"))
        if (
            not isinstance(pulse, dict)
            or pulse.get("type") not in {"COT_TWO_PULSE_TRAINS", "COFT_TWO_PULSE_TRAINS"}
            or any(pulse.get(key) in (None, "") for key in ("d1", "d2", "relation", "frequency_factor"))
            or "1-exp(-s*" not in factor_text.replace(" ", "")
        ):
            return _result("FAIL_COT_TWO_PULSE_TRAINS", [
                "COT/COFT sampled-data proof requires d1, d2, relation, and 1-exp(-s*T0)"
            ])

    modulator_io = proof.get("modulator_io")
    if not isinstance(modulator_io, dict) or any(
        modulator_io.get(key) in (None, "") for key in ("input", "output", "definition", "sign_convention")
    ):
        return _result("FAIL_MODULATOR_IO_MISSING", ["sampled-data proof requires modulator_io"])

    target_mapping = proof.get("target_mapping")
    if not isinstance(target_mapping, dict) or target_mapping.get("mapping_status") not in {
        "REGISTERED_DIRECT",
        "REGISTERED_DERIVED",
        "PROTOCOL_DERIVED_UNVERIFIED",
        "UNSUPPORTED",
    }:
        return _result("FAIL_TARGET_MAPPING", ["sampled-data proof requires target_mapping.mapping_status"])
    if target_mapping.get("mapping_status") == "UNSUPPORTED":
        return _result("FAIL_TARGET_MAPPING", ["unsupported sampled-data target cannot be reported as a checked transfer"])

    validation = proof.get("validation") or {}
    if validation.get("level") not in {
        "SAMPLED_DATA_CONTRACT_ONLY",
        "SAMPLED_DATA_REGISTERED_PARTIAL",
        "SAMPLED_DATA_REGISTERED_BENCHMARKED",
    }:
        return _result("FAIL_VALIDATION_LEVEL", ["sampled-data proof has invalid validation level"])
    return None


def _check_sampled_formula_objects(proof: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    model_id = (proof.get("classification") or {}).get("model_id")
    contract = get_paper_contract(model_id)
    expected_objects = contract["formula_objects"]
    actual_objects = proof.get("formula_object_bindings")
    if actual_objects != expected_objects:
        return ["formula_object_bindings do not match the registered paper contract"]
    sideband = proof.get("sideband") or {}
    if sideband.get("summation_definition") != contract.get("sideband_definition"):
        errors.append("sideband summation_definition does not match the paper contract")
    if contract.get("pulse_time_relation"):
        pulse = proof.get("pulse_structure") or {}
        if pulse.get("relation") != contract["pulse_time_relation"]:
            errors.append("pulse time-domain relation does not match the paper contract")
    bindings = proof.get("formula_bindings") or []
    by_id = {item.get("formula_id"): item for item in bindings if isinstance(item, dict)}
    for object_name, formula_id in expected_objects.items():
        if formula_id not in by_id:
            errors.append(f"{object_name}: missing registry binding {formula_id}")
            continue
        formula = get_formula(formula_id)
        if formula.get("source_model_id") != model_id:
            errors.append(f"{object_name}: formula model does not match {model_id}")
        errors.extend(check_binding(by_id[formula_id], None))

    object_expressions: dict[str, Any] = {
        "sampling": (proof.get("sampling") or {}).get("expression"),
        "Fm": (proof.get("Fm") or {}).get("expression"),
        "sideband": (proof.get("sideband") or {}).get("sum_expression"),
        "GPWM": (proof.get("modulator") or {}).get("expression"),
    }
    pulse = proof.get("pulse_structure") or {}
    if "pulse_relation" in expected_objects:
        object_expressions["pulse_relation"] = pulse.get("relation_expression")
    if "pulse_factor" in expected_objects:
        object_expressions["pulse_factor"] = pulse.get("frequency_factor")
    power_stage = proof.get("power_stage") or {}
    for name in ("Gid", "Gvd"):
        if name in expected_objects:
            object_expressions[name] = (power_stage.get(name) or {}).get("expression")
    transfer = proof.get("transfer") or {}
    requested = transfer.get("target_transfer")
    target_object = "GPWM" if requested == "Gm" else requested
    if target_object in expected_objects:
        object_expressions[target_object] = transfer.get("expression")
        if transfer.get("formula_id") != expected_objects[target_object]:
            errors.append(f"{target_object}: transfer formula_id does not match paper contract")

    for object_name, expression in object_expressions.items():
        formula_id = expected_objects.get(object_name)
        if not formula_id:
            continue
        binding = dict(by_id.get(formula_id, {}))
        binding["expression"] = expression
        object_errors = check_binding(binding, None) if binding.get("formula_id") else ["binding absent"]
        if object_errors:
            errors.append(f"{object_name}: " + "; ".join(object_errors))
    return errors


def check_proof_object(proof: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(proof, dict) or proof.get("proof_version") not in {"0.3.1", "0.4"}:
        return _result("FAIL_NOT_PROOF_OBJECT", ["proof_version=0.3.1 or 0.4 is required"])
    intake = proof.get("intake") or {}
    if intake.get("status") != "COMPLETE":
        return _result("FAIL_INCOMPLETE_INTAKE", ["intake status must be COMPLETE"])
    classification = proof.get("classification") or {}
    path = classification.get("path")
    if path not in REGISTERED_PATHS | {"PROTOCOL_DERIVED_NEW", SAMPLED_DATA_PATH}:
        return _result("FAIL_MISSING_CLASSIFICATION", ["recognized classification.path is required"])

    model_id = classification.get("model_id")
    transfer = proof.get("transfer") or {}
    target = transfer.get("target_transfer")
    modulator = proof.get("modulator") or {}
    registry = load_registry()

    if path == SAMPLED_DATA_PATH:
        sampled_error = _check_sampled_data_contract(proof)
        if sampled_error is not None:
            return sampled_error
        bindings = proof.get("formula_bindings")
        if not isinstance(bindings, list) or not bindings:
            return _result("FAIL_FORMULA_CONSISTENCY", ["sampled-data registered proof requires registry formula_bindings"])
        allowed_interfaces = {
            "sampled-data-sampling",
            "sampled-data-modulator",
            "sampled-data-sideband",
            "sampled-data-pulse",
            "sampled-data-power-stage",
            "sampled-data-target-mapping",
            "sampled-data-stability-boundary",
        }
        model_id = classification.get("model_id")
        for binding in bindings:
            formula = registry["formulas"].get(binding.get("formula_id"), {})
            if formula.get("source_model_id") != model_id or formula.get("interface") not in allowed_interfaces:
                return _result("FAIL_FORMULA_CONSISTENCY", [
                    f"{binding.get('formula_id')} is not a sampled-data registry binding for {model_id}"
                ])
        object_errors = _check_sampled_formula_objects(proof)
        if object_errors:
            return _result("FAIL_FORMULA_CONSISTENCY", object_errors)
        return _result("PASS", [])

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
        validate_artifact(proof, "proof_object.schema.json")
        if proof.get("proof_version") == "0.4":
            verify_workflow(proof, expected_state="FORMULA_BINDING")
        result = check_proof_object(proof)
    except (OSError, json.JSONDecodeError, FormulaRegistryError, ArtifactSchemaError, WorkflowError) as exc:
        result = _result("FAIL_NOT_PROOF_OBJECT", [str(exc)])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
