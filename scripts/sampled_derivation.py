#!/usr/bin/env python3
"""Generate the registered Yan sampled-data derivation artifact from a checked proof."""

from __future__ import annotations

from typing import Any

from artifact_workflow import attach_workflow, verify_workflow
from check_proof_object import check_proof_object
from formula_registry import get_formula, get_paper_contract


class SampledDerivationError(ValueError):
    """Raised when a proof cannot enter the registered derivation stage."""


def expand_registered_expressions(contract: dict[str, Any]) -> dict[str, str]:
    import sympy as sp

    expanded: dict[str, Any] = {}
    aliases = {"pulse_factor": "PulseFactor", "pulse_relation": "PulseRelation"}
    for object_name in contract["derivation_order"]:
        formula = get_formula(contract["formula_objects"][object_name])["canonical_sympy_expr"]
        names = {
            str(symbol)
            for prior in expanded.values()
            for symbol in prior.free_symbols
        } | set(expanded) | {"s", "exp", "pi"}
        local = {name: sp.Symbol(name) for name in names if name not in {"exp", "pi"}}
        local.update({"exp": sp.exp, "pi": sp.pi})
        expression = sp.sympify(formula, locals=local)
        substitutions = {}
        for name, value in expanded.items():
            symbol = sp.Symbol(aliases.get(name, name))
            if symbol in expression.free_symbols:
                substitutions[symbol] = value
        expanded[object_name] = sp.factor(expression.subs(substitutions))
    return {name: str(value) for name, value in expanded.items()}


def derive_sampled_transfer(proof: dict[str, Any]) -> dict[str, Any]:
    verify_workflow(proof, expected_state="FORMULA_BINDING")
    checked = check_proof_object(proof)
    if checked["status"] != "PASS":
        raise SampledDerivationError(
            f"proof object failed before derivation: {checked['status']}: "
            + "; ".join(checked["errors"])
        )
    classification = proof["classification"]
    if classification.get("path") != "SAMPLED_DATA_REGISTERED":
        raise SampledDerivationError("sampled derivation requires SAMPLED_DATA_REGISTERED proof")
    model_id = classification["model_id"]
    contract = get_paper_contract(model_id)
    formula_objects = contract["formula_objects"]
    expressions = {
        name: get_formula(formula_id)["canonical_sympy_expr"]
        for name, formula_id in formula_objects.items()
    }
    expanded_expressions = expand_registered_expressions(contract)
    control_contract = contract["control_contract"]
    selected_loop = "Ti" if control_contract == "current" else "Tv"
    target = proof["transfer"]["target_transfer"]
    target_object = "GPWM" if target == "Gm" else target
    if target_object not in expressions:
        raise SampledDerivationError(f"target {target} is not registered by {model_id}")
    response_kind = (
        "return_ratio" if target_object in {"Ti", "Tv", "Tloop"}
        else "closed_loop" if target_object == "Tc"
        else "transfer_function"
    )

    steps = []
    for index, object_name in enumerate(contract["derivation_order"], start=1):
        formula_id = formula_objects[object_name]
        formula = get_formula(formula_id)
        steps.append({
            "index": index,
            "object": object_name,
            "formula_id": formula_id,
            "expression": formula["canonical_sympy_expr"],
            "source_equation": formula["source_equation"],
            "approximation": formula["approximation"],
            "dimension_signature": formula["dimension_signature"],
        })

    artifact = {
        "derivation_version": "0.4",
        "case_id": proof["case_id"],
        "classification": classification,
        "control_contract": control_contract,
        "selected_loop": selected_loop,
        "target_transfer": target,
        "target_formula_id": formula_objects[target_object],
        "response_kind": response_kind,
        "expressions": expressions,
        "expanded_expressions": expanded_expressions,
        "expanded_target_expression": expanded_expressions[target_object],
        "reasoning_method": {
            "name": "12-step Yan sampled-data reasoning",
            "independent_derivation_path": [
                "1. identify control family and requested target",
                "2. declare sampling event and sampled variable",
                "3. write left and right limits",
                "4. apply Dirichlet sampled value",
                "5. derive or bind zero-ramp Fm from the sampled value",
                "6. construct pulse train relation",
                "7. construct pulse factor in the s-domain",
                "8. attach sideband summation policy",
                "9. build GPWM/Gm sampled modulator",
                "10. bind Buck ESR power stage Gid/Gvd",
                "11. form return ratio Ti/Tv and Tloop",
                "12. close the loop for Tc or Gvc and verify against registry",
            ],
            "registry_formula_path": [
                step["formula_id"] for step in steps
            ],
            "dual_path_check": "independent step composition must match registry-bound expanded_target_expression",
        },
        "steps": steps,
        "approximation_policy": {
            "declared": True,
            "items": sorted({step["approximation"] for step in steps}),
            "valid_frequency": "limited by sampled-data paper contract and benchmark metadata",
            "sideband": {
                key: proof["sideband"][key]
                for key in ("mode", "M", "indices", "include_zero", "numeric_approximation", "approximation")
                if key in proof["sideband"]
            },
        },
        "validation": {
            "level": proof["validation"]["level"],
            "completed": ["registry-bound-step-generation", "proof-expression-consistency"],
            "missing": list(proof["validation"].get("missing", [])),
        },
    }
    return attach_workflow(
        artifact,
        state="DERIVATION",
        intent=proof["workflow"]["intent"],
        predecessor=proof,
    )
