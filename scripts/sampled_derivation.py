#!/usr/bin/env python3
"""Generate the registered Yan sampled-data derivation artifact from a checked proof."""

from __future__ import annotations

from typing import Any

from artifact_workflow import attach_workflow, verify_workflow
from check_proof_object import check_proof_object
from formula_registry import get_formula, get_paper_contract


class SampledDerivationError(ValueError):
    """Raised when a proof cannot enter the registered derivation stage."""


def expand_registered_expressions(
    contract: dict[str, Any],
    *,
    object_overrides: dict[str, str] | None = None,
    simplify: bool = True,
) -> dict[str, str]:
    import sympy as sp

    expanded: dict[str, Any] = {}
    object_overrides = object_overrides or {}
    aliases = {"pulse_factor": "PulseFactor", "pulse_relation": "PulseRelation"}
    for object_name in contract["derivation_order"]:
        formula = object_overrides.get(
            object_name,
            get_formula(contract["formula_objects"][object_name])["canonical_sympy_expr"],
        )
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
            candidate_symbols = [sp.Symbol(aliases.get(name, name)), sp.Symbol(name)]
            if name == "sideband":
                candidate_symbols.extend([sp.Symbol("SidebandPulse"), sp.Symbol("SumG")])
            for symbol in candidate_symbols:
                if symbol in expression.free_symbols:
                    substitutions[symbol] = value
        substituted = expression.subs(substitutions)
        expanded[object_name] = sp.factor(substituted) if simplify else substituted
    return {name: str(value) for name, value in expanded.items()}


def numeric_sideband_overrides(proof: dict[str, Any]) -> dict[str, str]:
    import sympy as sp

    sideband = proof.get("sideband") or {}
    mode = sideband.get("mode")
    numeric = sideband.get("numeric_approximation")
    if mode in {"TRUNCATED_SUM_M", "PAPER_SIMPLIFIED_FORM"} and numeric:
        text = str(numeric)
        control_contract = proof.get("control_contract")
        power_stage = proof.get("power_stage") or {}
        stage_name = "Gid" if control_contract == "current" else "Gvd"
        stage = power_stage.get(stage_name) if isinstance(power_stage, dict) else None
        if isinstance(stage, dict) and "G(" in text:
            s = sp.Symbol("s")
            ws = sp.Symbol("ws")
            j = sp.I
            identifiers = set()
            import re

            for expression in (text, str(stage.get("expression", ""))):
                identifiers.update(re.findall(r"\b[A-Za-z_]\w*\b", expression))
            local = {
                name: sp.Symbol(name)
                for name in identifiers
                if name not in {"G", "exp", "sin", "cos", "sqrt", "pi", "j"}
            }
            local.update({"s": s, "ws": ws, "j": j, "exp": sp.exp, "sin": sp.sin, "cos": sp.cos, "sqrt": sp.sqrt, "pi": sp.pi})
            stage_expr = sp.sympify(stage["expression"], locals=local)

            def _g(argument: Any) -> Any:
                return stage_expr.subs(s, argument)

            local["G"] = _g
            text = str(sp.sympify(text, locals=local))
        return {"sideband": text}
    return {}


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
    numeric_overrides = numeric_sideband_overrides(proof)
    numeric_expanded_expressions = expand_registered_expressions(
        contract,
        object_overrides=numeric_overrides,
        simplify=False,
    )
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
    derivation_steps = [
        {
            "step_id": step["object"],
            "title": f"注册公式 {step['object']}",
            "latex": f"{step['object']}={step['expression']}",
            "explanation": f"该公式来自 formula_registry.yaml，source equation 为 {step['source_equation']}。",
            "source_artifact": "formula_registry.yaml",
            "latex_origin": "registry_binding",
            "provenance": step["formula_id"],
        }
        for step in steps
    ]

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
        "numeric_expanded_expressions": numeric_expanded_expressions,
        "numeric_expanded_target_expression": numeric_expanded_expressions[target_object],
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
                "11. form return ratio Ti/Tv",
                "12. close the loop for Tc or another explicitly registered target and verify against registry",
            ],
            "registry_formula_path": [
                step["formula_id"] for step in steps
            ],
            "dual_path_check": "independent step composition must match registry-bound expanded_target_expression",
        },
        "steps": steps,
        "derivation_steps": derivation_steps,
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
