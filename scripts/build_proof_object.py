#!/usr/bin/env python3
"""Build a v0.3.1 proof object from completed intake and classification artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from df_model_library import ModelError, generate_case
from formula_registry import formula_binding, get_formula, load_registry
from preflight_intake import IntakeGateError, require_complete_intake
from compensator_templates import CompensatorTemplateError, build_compensator
from sampled_modulator import build_sampled_modulator_proof
from artifact_workflow import WorkflowError, attach_workflow, verify_workflow
from schema_validation import ArtifactSchemaError, validate_artifact


class ProofBuildError(ValueError):
    """Raised when proof construction would invent or bypass evidence."""


COEFFICIENT_FORMULAS = {
    "cot-cm-li-lee-2010": {
        "a_c": "common.adapter.a-c", "a_g": "common.adapter.a-g",
        "a_o": "common.adapter.a-o", "a_i": "common.adapter.a-i",
    },
    "cot-cm-external-ramp-tian-2015": {
        "a_c": "common.adapter.a-c", "a_g": "common.adapter.a-g",
        "a_o": "common.adapter.a-o", "a_i": "common.adapter.a-i",
    },
    "rbcot-esr-lu-2023": {
        "a_c": "lu-2023.fdx", "a_g": "common.zero.a-g",
        "a_o": "lu-2023.a-o", "a_i": "common.adapter.a-i",
    },
}


def _registered_proof(
    normalized: dict[str, Any], classification: dict[str, Any]
) -> dict[str, Any]:
    model_id = classification.get("model_id") or (classification.get("model_match") or {}).get("model_id")
    if not model_id:
        raise ProofBuildError("Registered classification requires model_id.")
    target = normalized.get("target_transfer") or normalized.get("target")
    models = load_registry()["models"]
    if model_id not in models:
        raise ProofBuildError(f"Classification names unregistered model {model_id!r}.")
    model = models[model_id]
    if target not in model["supported_targets"]:
        raise ProofBuildError(f"Target {target} is not registered for {model_id}.")
    approximation = normalized.get("approximation")
    if not approximation:
        approximation = "pade" if classification["path"] == "DF_REGISTERED_DIRECT" else "exact"
    case = generate_case(model_id, normalized["parameters"], approximation)

    proof: dict[str, Any] = {
        "proof_version": "0.3.1",
        "case_id": normalized.get("case_id", model_id),
        "intake": {"status": "COMPLETE", "normalized": normalized},
        "classification": {"path": classification["path"], "model_id": model_id},
        "formula_bindings": case["formula_bindings"],
        "validation": {
            "level": "PAPER_GROUNDED_PARTIAL",
            "completed": ["formula-registry", "paper-benchmark"],
            "missing": ["switching-simulation"],
        },
    }
    if isinstance(normalized.get("sensing_layer"), dict):
        proof["sensing_layer"] = normalized["sensing_layer"]
    if classification["path"] == "DF_REGISTERED_DIRECT":
        transfer_binding = next(
            item for item in case["formula_bindings"]
            if target in get_formula(item["formula_id"])["supported_targets"]
            and item["formula_id"].startswith("li-lee-2009.gvc-")
        )
        proof["modulator"] = {"model_type": "direct-transfer"}
        proof["transfer"] = {
            "target_transfer": target,
            "formula_id": transfer_binding["formula_id"],
            "expression": case["paper_model"][target],
        }
    else:
        coefficient_ids = COEFFICIENT_FORMULAS[model_id]
        from df_buck_sympy import derive_model

        derived = derive_model(case)
        proof["modulator"] = {
            "model_type": "a-star",
            "coefficients": {
                name: {"formula_id": coefficient_ids[name], "expression": expression}
                for name, expression in case["modulator"].items()
            },
        }
        proof["transfer"] = {
            "target_transfer": target,
            "formula_id": None,
            "expression": str(derived["evaluated"][target]),
            "origin": "registered-buck-sympy-elimination",
        }
    if isinstance(normalized.get("compensator"), dict):
        proof["compensator"] = build_compensator(normalized["compensator"])
    if isinstance(normalized.get("loop_break"), dict):
        proof["loop_break"] = normalized["loop_break"]
    return proof


def build_proof_object(
    intake_artifact: dict[str, Any], classification: dict[str, Any]
) -> dict[str, Any]:
    normalized = require_complete_intake(intake_artifact)
    path = classification.get("path")
    v04 = intake_artifact.get("intake_version") == "0.4"
    if v04:
        verify_workflow(intake_artifact, expected_state="PREFLIGHT_INTAKE")
        verify_workflow(classification, expected_state="MODEL_CLASSIFY", predecessor=intake_artifact)
    if path in {"DF_REGISTERED_DIRECT", "DF_REGISTERED_MULTIPORT"}:
        proof = _registered_proof(normalized, classification)
        if v04:
            proof["proof_version"] = "0.4"
            proof = attach_workflow(proof, state="FORMULA_BINDING", intent=intake_artifact["workflow"]["intent"], predecessor=classification)
        validate_artifact(proof, "proof_object.schema.json")
        return proof
    if path == "SAMPLED_DATA_REGISTERED":
        spec = {
            **normalized,
            "part_family": classification.get("part_family"),
            "model_id": classification.get("model_id"),
        }
        sampled = build_sampled_modulator_proof(spec)
        if sampled.get("status") != "OK":
            status = sampled.get("status", "sampled-data proof construction failed")
            if status == "REJECT_TARGET_NOT_REGISTERED":
                raise ProofBuildError(
                    f"Target {sampled.get('target')} is not registered for {sampled.get('model_id')}."
                )
            raise ProofBuildError(status)
        target = normalized.get("target_transfer") or normalized.get("target")
        formula_object_bindings = sampled["formula_objects"]
        binding_ids = list(dict.fromkeys(formula_object_bindings.values()))
        target_formula_id = sampled["target_formula_id"]
        target_expression = get_formula(target_formula_id)["canonical_sympy_expr"]
        proof = {
            "proof_version": "0.4",
            "case_id": normalized.get("case_id", classification.get("model_id", "sampled-data-case")),
            "intake": {"status": "COMPLETE", "normalized": normalized},
            "classification": {
                "path": path,
                "part_family": classification.get("part_family"),
                "model_id": classification.get("model_id"),
            },
            "formula_bindings": [formula_binding(formula_id) for formula_id in binding_ids],
            "formula_object_bindings": formula_object_bindings,
            "control_contract": sampled["control_contract"],
            "sampling": sampled["sampling"],
            "pulse_structure": sampled["pulse_structure"],
            "Fm": sampled["Fm"],
            "sideband": sampled["sideband"],
            "modulator_io": sampled["modulator_io"],
            "target_mapping": sampled["target_mapping"],
            "power_stage": sampled["power_stage"],
            "modulator": sampled["modulator"],
            "transfer": {
                "target_transfer": target,
                "formula_id": target_formula_id,
                "expression": target_expression,
                "origin": "sampled-data-registry-binding; final algebra belongs to derivation artifact",
            },
            "validation": {
                "level": classification.get("validation_level", "SAMPLED_DATA_REGISTERED_PARTIAL"),
                "completed": [
                    "sampled-data-contract",
                    "dirichlet-reference",
                    "cot-pulse-structure" if "PART_II" in str(classification.get("part_family")) else "single-pulse-structure",
                ],
                "missing": ["paper-figure-reproduction", "switching-simulation"],
            },
        }
        if isinstance(normalized.get("sensing_layer"), dict):
            proof["sensing_layer"] = normalized["sensing_layer"]
        if v04:
            proof = attach_workflow(proof, state="FORMULA_BINDING", intent=intake_artifact["workflow"]["intent"], predecessor=classification)
        validate_artifact(proof, "proof_object.schema.json")
        return proof
    if path == "UNSUPPORTED" and any(
        str(item).startswith("TARGET_NOT_REGISTERED:")
        for item in classification.get("unsupported_effects", [])
    ):
        raise ProofBuildError(
            f"Target {normalized.get('target_transfer') or normalized.get('target')} is not registered "
            f"for {classification.get('model_id')}."
        )
    if path != "PROTOCOL_DERIVED_NEW":
        raise ProofBuildError(f"Cannot build proof object for classification path {path!r}.")
    relation = normalized.get("df_relation")
    if not isinstance(relation, dict) or not relation.get("form"):
        raise ProofBuildError("Protocol-derived proof requires df_relation.form.")
    proof = {
        "proof_version": "0.3.1",
        "case_id": normalized.get("case_id", "protocol-derived-case"),
        "intake": {"status": "COMPLETE", "normalized": normalized},
        "classification": {"path": path, "model_id": None},
        "formula_bindings": [],
        "modulator": {"model_type": "protocol-derived", "relation": relation},
        "transfer": {
            "target_transfer": normalized["target_transfer"],
            "formula_id": None,
            "expression": normalized.get("transfer_function", "candidate; derivation pending"),
        },
        "validation": {
            "level": "PROTOCOL_DERIVED_UNVERIFIED",
            "completed": ["protocol-completeness"],
            "missing": ["paper-benchmark", "switching-simulation"],
        },
    }
    if isinstance(normalized.get("sensing_layer"), dict):
        proof["sensing_layer"] = normalized["sensing_layer"]
    if v04:
        proof["proof_version"] = "0.4"
        proof = attach_workflow(proof, state="FORMULA_BINDING", intent=intake_artifact["workflow"]["intent"], predecessor=classification)
    validate_artifact(proof, "proof_object.schema.json")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an ESSF v0.3.1 proof object.")
    parser.add_argument("--intake-status", required=True)
    parser.add_argument("--classification", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        intake = json.loads(Path(args.intake_status).read_text(encoding="utf-8"))
        classification = json.loads(Path(args.classification).read_text(encoding="utf-8"))
        proof = build_proof_object(intake, classification)
        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote proof object: {output.resolve()}")
        return 0
    except (OSError, json.JSONDecodeError, IntakeGateError, ModelError, ProofBuildError, CompensatorTemplateError, ArtifactSchemaError, WorkflowError) as exc:
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
