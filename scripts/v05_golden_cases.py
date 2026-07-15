#!/usr/bin/env python3
"""Deterministic confirmed inputs for the four v0.5 CCM Buck golden families."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from circuit_ir import DIMENSIONS, attach_proposed_ir, build_image_intake, confirm_circuit_ir, render_checkout
from physics_spec import confirm_physics_spec
from physics_workflow import attach_physics_workflow


FAMILIES = {
    "v2-cot": {"guard": "v_vo-v_control", "uc": 1.164, "comparator_negative": "vo"},
    "current-mode-cot": {"guard": "0.1*i_L-v_control", "uc": 0.6, "comparator_negative": "sw"},
    "external-ramp-cot": {"guard": "0.1*i_L+v_vramp-v_control", "uc": 0.9, "comparator_negative": "vramp"},
    "esr-ripple-rbcot": {"guard": "v_vo-v_control", "uc": 1.164, "comparator_negative": "vo"},
}


def _quantity(magnitude: float, unit: str) -> dict[str, Any]:
    return {
        "magnitude": magnitude, "unit": unit, "si_dimension": DIMENSIONS[unit],
        "source": "registry_fixture",
    }


def _orientation() -> dict[str, str]:
    return {"voltage_positive": "p", "voltage_negative": "n", "current_from": "p", "current_to": "n"}


def _component(
    component_id: str, kind: str, p: str, n: str, *, value: dict[str, Any] | None = None,
    parameters: dict[str, Any] | None = None, bbox: list[float] | None = None,
) -> dict[str, Any]:
    result = {
        "id": component_id, "type": kind, "terminals": {"p": p, "n": n},
        "orientation": _orientation(), "bbox": bbox or [0.1, 0.1, 0.2, 0.2],
        "confidence": 1.0, "source_evidence": "numbered golden schematic plus fixture declaration",
    }
    if value is not None:
        result["value"] = value
    if parameters:
        result["parameters"] = parameters
    return result


def _image_intake(family: str, image_path: Path | None) -> dict[str, Any]:
    case_id = f"v05-golden-{family}"
    if image_path is not None:
        return build_image_intake(image_path, case_id)
    digest = hashlib.sha256(f"{family}-schematic-forward-test-fixture".encode()).hexdigest()
    return attach_physics_workflow({
        "intake_version": "0.5", "case_id": case_id,
        "source_image": {"filename": f"{family}.fixture", "sha256": digest, "width_px": 960, "height_px": 540},
        "rule": "golden forward-test image provenance fixture",
    }, state="IMAGE_INTAKE")


def build_golden_case(
    family: str, *, image_path: Path | None = None, include_registry_crosscheck: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if family not in FAMILIES:
        raise ValueError(f"unknown family {family}; choose from {', '.join(FAMILIES)}")
    config = FAMILIES[family]
    intake = _image_intake(family, image_path)
    nets = ["gnd", "vin", "sw", "vo", "vc", "control"]
    net_regions = {
        "gnd": [0.86, 0.82, 0.92, 0.90],
        "vin": [0.08, 0.18, 0.25, 0.25],
        "sw": [0.40, 0.37, 0.47, 0.44],
        "vo": [0.66, 0.36, 0.72, 0.43],
        "vc": [0.67, 0.57, 0.72, 0.64],
        "control": [0.51, 0.16, 0.58, 0.25],
        "vramp": [0.48, 0.72, 0.58, 0.84],
    }
    components = [
        _component("VG", "voltage_source", "vin", "gnd", value=_quantity(12.0, "V"), parameters={"input": "vg", "gain": 1.0, "dc": 0.0}, bbox=[0.04, 0.38, 0.13, 0.56]),
        _component("VCTRL", "voltage_source", "control", "gnd", value=_quantity(float(config["uc"]), "V"), parameters={"input": "uc", "gain": 1.0, "dc": 0.0}, bbox=[0.51, 0.14, 0.57, 0.26]),
        _component("QH", "ideal_switch", "vin", "sw", bbox=[0.25, 0.16, 0.36, 0.28]),
        _component("QL", "ideal_switch", "sw", "gnd", bbox=[0.37, 0.52, 0.48, 0.64]),
        _component("L", "inductor", "sw", "vo", value=_quantity(300e-9, "H"), parameters={"series_resistance": 0.0}, bbox=[0.47, 0.34, 0.59, 0.46]),
        _component("RESR", "resistor", "vo", "vc", value=_quantity(6e-3, "ohm"), parameters={"role": "ESR"}, bbox=[0.65, 0.47, 0.72, 0.58]),
        _component("C", "capacitor", "vc", "gnd", value=_quantity(560e-6, "F"), bbox=[0.64, 0.61, 0.73, 0.68]),
        _component("RLOAD", "resistor", "vo", "gnd", value=_quantity(0.1, "ohm"), parameters={"role": "load"}, bbox=[0.76, 0.48, 0.84, 0.69]),
    ]
    if family == "external-ramp-cot":
        nets.append("vramp")
        components.append(_component(
            "RAMP", "ramp", "vramp", "gnd", parameters={"slope": 1e5, "active_modes": ["off"]},
            bbox=[0.48, 0.73, 0.58, 0.84],
        ))
    comparator = {
        "id": "CMP", "type": "comparator",
        "terminals": {"positive": "control", "negative": str(config["comparator_negative"])},
        "parameters": {
            "positive_expression": "v_control",
            "negative_expression": config["guard"].replace("-v_control", ""),
            "guard_expression": config["guard"], "output_semantics": "turn-on request",
        },
        "bbox": [0.62, 0.17, 0.73, 0.35], "confidence": 1.0,
        "source_evidence": "visible comparator polarity and confirmed guard expression",
    }
    components.append(comparator)
    raw_ir = {
        "ir_version": "0.5", "case_id": intake["case_id"], "status": "PROPOSED",
        "source_image": intake["source_image"], "ground_net": "gnd",
        "nets": [{"id": net, "aliases": [], "evidence_regions": [net_regions[net]]} for net in nets],
        "components": components,
        "ports": [
            {"name": "uc", "role": "input", "quantity": "control voltage", "expression": "v_control", "sign_convention": "positive raises the comparator threshold"},
            {"name": "vg", "role": "input", "quantity": "input voltage", "expression": "v_vin", "sign_convention": "positive from VIN to ground"},
            {"name": "vo", "role": "output", "quantity": "output voltage", "expression": "v_vo", "sign_convention": "positive from VO to ground"},
        ],
        "ambiguities": [],
    }
    proposed = attach_proposed_ir(raw_ir, intake)
    circuit_ir = confirm_circuit_ir(proposed, notes=[f"golden {family} topology and comparator semantics confirmed"])
    fixed_termination: dict[str, Any] = {
        "type": "fixed_duration", "duration": 333.33e-9, "parameter_name": "Ton",
    }
    initial_state = {"i_L": 6.0, "v_vc": 1.2}
    if family == "external-ramp-cot":
        fixed_termination["reset"] = {"assignments": {"x_RAMP_0": 0.0}}
        initial_state["x_RAMP_0"] = 0.3
    raw_spec: dict[str, Any] = {
        "topology": "single-phase-buck", "operating_mode": "CCM",
        "target": {"name": "Gvc", "input": "uc", "output": "vo", "response_kind": "transfer_function"},
        "inputs": {"uc": float(config["uc"]), "vg": 12.0},
        "modes": [
            {"id": "on", "switch_states": {"QH": "ON", "QL": "OFF"}},
            {"id": "off", "switch_states": {"QH": "OFF", "QL": "ON"}},
        ],
        "mode_sequence": [
            {"mode": "on", "termination": fixed_termination},
            {"mode": "off", "termination": {"type": "guard", "expression": config["guard"], "direction": -1, "min_duration": 1e-9, "max_duration": 10e-6}},
        ],
        "fidelity": "declared_nonideal", "approximations": ["ideal synchronous switches"],
        "initial_state": initial_state, "overrides": [],
        "analysis": {"max_hz": 100e3, "points": 41, "sideband_probe_points": 7, "sideband_max_m": 64, "finite_difference_step": 1e-6, "sensitivity_step": 1e-4},
    }
    if include_registry_crosscheck:
        model = {
            "v2-cot": ("v2-cot-li-lee-2009", "pade", {}),
            "current-mode-cot": ("cot-cm-li-lee-2010", "pade", {"Ri": 0.1}),
            "external-ramp-cot": ("cot-cm-external-ramp-tian-2015", "exact", {"Ri": 0.1, "se_ratio": 0.25}),
            "esr-ripple-rbcot": ("rbcot-esr-lu-2023", "pade", {}),
        }[family]
        raw_spec["registry_crosscheck"] = {
            "model_id": model[0], "approximation": model[1],
            "parameters": {"Vin": 12.0, "Vo": 1.2, "fs": 300e3, "L": 300e-9, "C": 560e-6, "R": 0.1, "rC": 6e-3, "rL": 0.0, **model[2]},
            "valid_min_hz": 250.0,
            "valid_max_hz": 1500.0 if family == "external-ramp-cot" else 10e3,
            "comparison_kind": "normalised-trend" if family in {"external-ramp-cot", "esr-ripple-rbcot"} else "absolute-transfer",
        }
    physics_spec = confirm_physics_spec(raw_spec, circuit_ir)
    return intake, circuit_ir, physics_spec


def main() -> int:
    parser = argparse.ArgumentParser(description="Create confirmed v0.5 golden inputs.")
    parser.add_argument("--family", choices=sorted(FAMILIES), required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--image")
    parser.add_argument("--registry-crosscheck", action="store_true")
    args = parser.parse_args()
    try:
        out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
        intake, circuit, spec = build_golden_case(
            args.family, image_path=Path(args.image) if args.image else None,
            include_registry_crosscheck=args.registry_crosscheck,
        )
        for name, artifact in (("image_intake.json", intake), ("circuit_ir.json", circuit), ("physics_spec.json", spec)):
            (out / name).write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        if args.image:
            suffix = ".svg" if Path(args.image).suffix.lower() == ".svg" else ".png"
            render_checkout(circuit, Path(args.image), out / f"circuit_checkout{suffix}")
        print("PASS")
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
