#!/usr/bin/env python3
"""v0.4 sampled-data modulator contract helpers."""

from __future__ import annotations

from typing import Any

from cot_pulse_train import build_cot_pulse_structure
from fm_models import build_fm_model
from sideband_sum import build_sideband
from formula_registry import get_formula, get_paper_contract, model_specs


def build_target_mapping(
    *,
    available_outputs: list[str],
    requested_target: str,
    rules: dict[str, str],
) -> dict[str, Any]:
    direct_outputs = {"Gm", "GPWM"}
    if requested_target in available_outputs and requested_target in direct_outputs:
        status = "REGISTERED_DIRECT"
        rule = rules.get(requested_target, "registered direct sampled-data output")
    elif requested_target in rules:
        status = "REGISTERED_DERIVED"
        rule = rules[requested_target]
    else:
        status = "UNSUPPORTED"
        rule = f"{requested_target} is not registered for this sampled-data model"
    return {
        "available_registered_outputs": available_outputs,
        "requested_target": requested_target,
        "mapping_rule": rule,
        "mapping_status": status,
    }


def build_sampling_contract(*, sampled_variable: str, sampling_instant: str) -> dict[str, Any]:
    return {
        "sampling_instant": sampling_instant,
        "sampled_variable": sampled_variable,
        "left_limit": f"{sampled_variable}(k-)",
        "right_limit": f"{sampled_variable}(k+)",
        "dirichlet_value": f"({sampled_variable}(k-)+{sampled_variable}(k+))/2",
        "dirichlet_required": True,
    }


def build_sampled_modulator_proof(spec: dict[str, Any]) -> dict[str, Any]:
    family = spec["part_family"]
    model_id = spec["model_id"]
    contract = get_paper_contract(model_id)
    formula_objects = contract["formula_objects"]
    model = model_specs()[model_id]
    sampled_variable = spec.get("sampled_variable", "is")
    target = spec.get("target_transfer", "Gm")
    if target not in model["supported_targets"]:
        return {"status": "REJECT_TARGET_NOT_REGISTERED", "target": target, "model_id": model_id}
    sampling = build_sampling_contract(
        sampled_variable=sampled_variable,
        sampling_instant=spec.get("sampling_instant", "modulator input intersection"),
    )
    sampling["formula_id"] = formula_objects["sampling"]
    sampling["expression"] = get_formula(formula_objects["sampling"])["canonical_sympy_expr"]
    sampling["dirichlet_value"] = sampling["expression"]
    fm = build_fm_model(spec)
    if fm["status"] != "OK":
        return fm
    fm["Fm"]["formula_id"] = formula_objects["Fm"]
    fm["Fm"]["expression"] = get_formula(formula_objects["Fm"])["canonical_sympy_expr"]
    if family in {
        "SAMPLED_DATA_REGISTERED_PART_II_CCOT_CCOFT",
        "SAMPLED_DATA_REGISTERED_PART_II_VCOT_VCOFT",
    }:
        pulse = build_cot_pulse_structure({
            "control_family": spec.get("control_family", "C-COT"),
            "fixed_interval": spec.get("fixed_interval", "Ton"),
        })
        pulse["relation_formula_id"] = formula_objects["pulse_relation"]
        pulse["relation_expression"] = get_formula(formula_objects["pulse_relation"])["canonical_sympy_expr"]
        pulse["relation"] = contract["pulse_time_relation"]
        pulse["factor_formula_id"] = formula_objects["pulse_factor"]
        pulse["frequency_factor"] = get_formula(formula_objects["pulse_factor"])["canonical_sympy_expr"]
    else:
        pulse = {"type": "SINGLE_PULSE_TRAIN", "frequency_factor": "1"}
    sideband_spec = dict(spec.get("sideband") or {"mode": "SYMBOLIC_FULL_SUM"})
    sideband_spec.setdefault(
        "base_expression",
        "G(s+j*n*ws)*(1-exp(-(s+j*n*ws)*T0))" if "PART_II" in family else "G(s+j*n*ws)",
    )
    sideband = build_sideband(sideband_spec)
    sideband["formula_id"] = formula_objects["sideband"]
    if sideband.get("numeric_expression"):
        sideband["numeric_approximation"] = sideband["numeric_expression"]
    sideband["summation_definition"] = contract["sideband_definition"]
    sideband["sum_expression"] = get_formula(formula_objects["sideband"])["canonical_sympy_expr"]
    available_outputs = list(model["supported_targets"])
    loop_name = "Ti" if contract["control_contract"] == "current" else "Tv"
    plant_name = "Gid" if contract["control_contract"] == "current" else "Gvd"
    rules = {
        loop_name: f"{loop_name}={'Hi*Gid*GPWM' if loop_name == 'Ti' else 'Hv*Gvd*GPWM'}",
        "Tloop": f"Tloop={loop_name}",
        "Tc": f"Tc={loop_name}/(1+{loop_name})",
        "Gvc": f"Gvc={plant_name}*GPWM/(1+{loop_name})",
    }
    mapping = build_target_mapping(
        available_outputs=available_outputs,
        requested_target=target,
        rules=rules,
    )
    return {
        "status": "OK",
        "formula_id": formula_objects["GPWM"],
        "formula_objects": formula_objects,
        "control_contract": contract["control_contract"],
        "sampling": sampling,
        "pulse_structure": pulse,
        "Fm": fm["Fm"],
        "sideband": sideband,
        "modulator_io": {
            "input": sampled_variable,
            "output": "dsum" if pulse["type"] != "SINGLE_PULSE_TRAIN" else "d",
            "definition": spec.get("modulator_definition", f"Gm=-d_hat/{sampled_variable}_hat"),
            "sign_convention": spec.get("sign_convention", "negative"),
        },
        "target_mapping": mapping,
        "power_stage": {
            name: {
                "formula_id": formula_objects[name],
                "expression": get_formula(formula_objects[name])["canonical_sympy_expr"],
                "approximation": get_formula(formula_objects[name])["approximation"],
            }
            for name in ("Gid", "Gvd") if name in formula_objects
        },
        "modulator": {
            "model_type": "GPWM",
            "formula_id": formula_objects["GPWM"],
            "expression": get_formula(formula_objects["GPWM"])["canonical_sympy_expr"],
            "origin": "sampled_data_registered",
        },
        "target_formula_id": formula_objects[target if target != "Gm" else "GPWM"],
    }


def _formula_id_for_family(family: str, control_family: str) -> str:
    if family == "SAMPLED_DATA_REGISTERED_PART_I_PCM_VCM_PVM_VVM":
        return "yan-2022-part-i.pcm-fm-zero-ramp"
    text = str(control_family).upper()
    if family == "SAMPLED_DATA_REGISTERED_PART_II_VCOT_VCOFT" or text.startswith("V-"):
        return "yan-2022-part-ii.vcot-gpwm-pulse-factor"
    return "yan-2022-part-ii.ccot-gpwm-pulse-factor"
