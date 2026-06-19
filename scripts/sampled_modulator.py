#!/usr/bin/env python3
"""v0.4 sampled-data modulator contract helpers."""

from __future__ import annotations

from typing import Any

from cot_pulse_train import build_cot_pulse_structure
from fm_models import build_fm_model
from sideband_sum import build_sideband


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
    sampled_variable = spec.get("sampled_variable", "is")
    target = spec.get("target_transfer", "Gm")
    sampling = build_sampling_contract(
        sampled_variable=sampled_variable,
        sampling_instant=spec.get("sampling_instant", "modulator input intersection"),
    )
    fm = build_fm_model(spec)
    if fm["status"] != "OK":
        return fm
    if family in {
        "SAMPLED_DATA_REGISTERED_PART_II_CCOT_CCOFT",
        "SAMPLED_DATA_REGISTERED_PART_II_VCOT_VCOFT",
    }:
        pulse = build_cot_pulse_structure({
            "control_family": spec.get("control_family", "C-COT"),
            "fixed_interval": spec.get("fixed_interval", "Ton"),
        })
        modulator_expr = f"({fm['Fm']['expression']})*({pulse['frequency_factor']})"
    else:
        pulse = {"type": "SINGLE_PULSE_TRAIN", "frequency_factor": "1"}
        modulator_expr = fm["Fm"]["expression"]
    sideband = build_sideband(spec.get("sideband", {"mode": "SYMBOLIC_FULL_SUM", "base_expression": "Gid(s+j*n*ws)"}))
    available_outputs = spec.get("available_outputs", ["Gm"])
    rules = spec.get("target_rules", {})
    mapping = build_target_mapping(
        available_outputs=available_outputs,
        requested_target=target,
        rules=rules,
    )
    return {
        "status": "OK",
        "formula_id": _formula_id_for_family(family, spec.get("control_family", "C-COT")),
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
        "modulator": {
            "model_type": "Gm",
            "expression": modulator_expr,
            "origin": "sampled_data_registered",
        },
    }


def _formula_id_for_family(family: str, control_family: str) -> str:
    if family == "SAMPLED_DATA_REGISTERED_PART_I_PCM_VCM_PVM_VVM":
        return "yan-2022-part-i.pcm-fm-zero-ramp"
    text = str(control_family).upper()
    if family == "SAMPLED_DATA_REGISTERED_PART_II_VCOT_VCOFT" or text.startswith("V-"):
        return "yan-2022-part-ii.vcot-gpwm-pulse-factor"
    return "yan-2022-part-ii.ccot-gpwm-pulse-factor"
