#!/usr/bin/env python3
"""Paper-grounded model registry for single-phase Buck DF models."""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from formula_registry import bind_expression, formula_binding, model_specs


class ModelError(ValueError):
    """Raised when a requested paper model is unsupported or invalid."""


MODEL_SPECS = {
    model_id: spec
    for model_id, spec in model_specs().items()
    if spec.get("method") == "describing-function"
}

EXCLUDED_MODELS = {
    "rbcot-internal-ramp-huang-2025": (
        "Huang et al. 2025 explicitly uses an average model with delay correction; "
        "the average model is excluded from this DF-only v0.2 library."
    )
}


def list_models() -> list[str]:
    return sorted(MODEL_SPECS)


def current_source_to_duty_coefficients(*, Fc: str, Fg: str, Fo: str) -> dict[str, str]:
    """Adapt a closed current-source DF relation to the Buck duty interface."""

    return {
        "a_c": bind_expression("common.adapter.a-c", Fc=Fc),
        "a_g": bind_expression("common.adapter.a-g", Fg=Fg),
        "a_o": bind_expression("common.adapter.a-o", Fo=Fo),
        "a_i": bind_expression("common.adapter.a-i"),
        "coefficient_origin": "derived-adapter",
    }


def _adapter_formula_bindings(
    adapted: dict[str, str], *, Fc: str, Fg: str, Fo: str
) -> list[dict[str, Any]]:
    return [
        formula_binding("common.adapter.a-c", adapted["a_c"], {"Fc": Fc}),
        formula_binding("common.adapter.a-g", adapted["a_g"], {"Fg": Fg}),
        formula_binding("common.adapter.a-o", adapted["a_o"], {"Fo": Fo}),
        formula_binding("common.adapter.a-i", adapted["a_i"]),
    ]


def _require(parameters: dict[str, Any], names: tuple[str, ...]) -> None:
    missing = [name for name in names if name not in parameters]
    if missing:
        raise ModelError(f"Missing required parameters: {', '.join(missing)}")


def _positive(parameters: dict[str, Any], names: tuple[str, ...]) -> None:
    invalid = [name for name in names if float(parameters[name]) <= 0]
    if invalid:
        raise ModelError(f"Parameters must be positive: {', '.join(invalid)}")


def _base_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    if int(parameters.get("phases", 1)) != 1:
        raise ModelError("v0.2 supports single-phase Buck models only.")
    if str(parameters.get("operating_mode", "CCM")).upper() != "CCM":
        raise ModelError("v0.2 supports CCM only; DCM is outside the model boundary.")
    if bool(parameters.get("pulse_skipping", False)):
        raise ModelError("pulse skipping is outside the v0.2 model boundary.")
    required = ("Vin", "Vo", "fs", "L", "C", "R", "rC")
    _require(parameters, required)
    _positive(parameters, required)
    vin = float(parameters["Vin"])
    vo = float(parameters["Vo"])
    if not 0 < vo < vin:
        raise ModelError("Buck CCM models require 0 < Vo < Vin.")
    fs = float(parameters["fs"])
    duty = vo / vin
    result = dict(parameters)
    result.update(
        {
            "Vg": vin,
            "D": duty,
            "Tsw": 1 / fs,
            "Ton": duty / fs,
            "rL": float(parameters.get("rL", 0.0)),
        }
    )
    return result


def _paper_case(
    *,
    model_id: str,
    parameters: dict[str, Any],
    modulator: dict[str, str] | None,
    paper_model: dict[str, str],
    valid_frequency: dict[str, Any],
    coefficient_origin: str,
    component_fidelity: dict[str, str],
    formula_bindings: list[dict[str, Any]],
) -> dict[str, Any]:
    case: dict[str, Any] = {
        "name": model_id,
        "model_id": model_id,
        "method": "describing-function",
        "topology": "buck-ccm",
        "phases": 1,
        "df_source": MODEL_SPECS[model_id]["source"],
        "valid_frequency": valid_frequency,
        "parameters": parameters,
        "paper_model": paper_model,
        "coefficient_origin": coefficient_origin,
        "component_fidelity": component_fidelity,
        "targets": list(MODEL_SPECS[model_id]["supported_targets"]),
        "formula_bindings": formula_bindings,
    }
    if modulator is not None:
        case["modulator"] = modulator
    return case


def _li_lee_2010(parameters: dict[str, Any], approximation: str) -> dict[str, Any]:
    p = _base_parameters(parameters)
    _require(p, ("Ri",))
    _positive(p, ("Ri",))
    p.update(
        {
            "sf": float(p["Ri"]) * float(p["Vo"]) / float(p["L"]),
            "w1": "pi/Ton",
            "Q1": "2/pi",
        }
    )
    if approximation == "exact":
        fc_id = "li-lee-2010.fc-exact"
        fc = bind_expression(fc_id)
        basis = "Li-Lee-2010-Eq9"
    elif approximation == "pade":
        fc_id = "li-lee-2010.fc-pade"
        fc = bind_expression(fc_id)
        basis = "Li-Lee-2010-Eq10"
    else:
        raise ModelError("Li/Lee 2010 approximation must be 'exact' or 'pade'.")

    k1 = bind_expression("li-lee-2010.k1")
    k2 = bind_expression("li-lee-2010.k2")
    fg = bind_expression("li-lee-2010.fg", k1=k1, Fc=fc)
    fo = bind_expression("li-lee-2010.fo", k2=k2, Fc=fc)
    adapted = current_source_to_duty_coefficients(Fc=fc, Fg=fg, Fo=fo)
    origin = adapted.pop("coefficient_origin")
    return _paper_case(
        model_id="cot-cm-li-lee-2010",
        parameters=p,
        modulator=adapted,
        paper_model={"Fc": fc, "Fg": fg, "Fo": fo, "k1": k1, "k2": k2},
        valid_frequency={
            "max_hz": float(p["fs"]) / 2,
            "basis": basis,
            "paper_pade_limit_hz": 1 / (2 * float(p["Ton"])),
            "excluded_frequencies": "fm = n*fs/2",
        },
        coefficient_origin=origin,
        component_fidelity={
            "Fc": "paper-equation",
            "Fg": "paper-low-order-ratio-Eq14",
            "Fo": "paper-low-order-ratio-Eq15",
            "a_*": "derived-adapter",
        },
        formula_bindings=[
            formula_binding(fc_id, fc),
            formula_binding("li-lee-2010.k1", k1),
            formula_binding("li-lee-2010.k2", k2),
            formula_binding("li-lee-2010.fg", fg, {"k1": k1, "Fc": fc}),
            formula_binding("li-lee-2010.fo", fo, {"k2": k2, "Fc": fc}),
            *_adapter_formula_bindings(adapted, Fc=fc, Fg=fg, Fo=fo),
        ],
    )


def _tian_external_ramp(parameters: dict[str, Any], approximation: str) -> dict[str, Any]:
    if approximation != "exact":
        raise ModelError(
            "Tian external-ramp cases emit the exact multi-input DF; "
            "the Eq. (8) low-order control path is included as Fc_low_order."
        )
    p = _base_parameters(parameters)
    _require(p, ("Ri", "se_ratio"))
    _positive(p, ("Ri",))
    se_ratio = float(p["se_ratio"])
    if se_ratio < 0:
        raise ModelError("se_ratio must be non-negative.")
    sf = float(p["Ri"]) * float(p["Vo"]) / float(p["L"])
    p.update({"sf": sf, "se": se_ratio * sf})

    denominator = bind_expression("tian-2015.a")
    fc = bind_expression("tian-2015.fc", A=denominator)
    fg = bind_expression("tian-2015.fg", A=denominator)
    fo = bind_expression("tian-2015.fo", A=denominator)
    fc_low = bind_expression("tian-2015.fc-low")
    adapted = current_source_to_duty_coefficients(Fc=fc, Fg=fg, Fo=fo)
    origin = adapted.pop("coefficient_origin")
    case = _paper_case(
        model_id="cot-cm-external-ramp-tian-2015",
        parameters=p,
        modulator=adapted,
        paper_model={"Fc": fc, "Fg": fg, "Fo": fo, "Fc_low_order": fc_low},
        valid_frequency={
            "max_hz": float(p["fs"]) / 2,
            "basis": "Tian-2015-Eq8-and-validation",
            "approximation": "Eq. (8) first-order control-current path",
        },
        coefficient_origin=origin,
        component_fidelity={
            "Fc": "paper-equation-4",
            "Fg": "paper-equation-6",
            "Fo": "paper-equation-7",
            "Fc_low_order": "paper-equation-8",
            "a_*": "derived-adapter",
        },
        formula_bindings=[
            formula_binding("tian-2015.a", denominator),
            formula_binding("tian-2015.fc", fc, {"A": denominator}),
            formula_binding("tian-2015.fg", fg, {"A": denominator}),
            formula_binding("tian-2015.fo", fo, {"A": denominator}),
            formula_binding("tian-2015.fc-low", fc_low),
            *_adapter_formula_bindings(adapted, Fc=fc, Fg=fg, Fo=fo),
        ],
    )
    case["features_hz"] = {
        "moving_pole": float(p["fs"]) / (math.pi * (2 * se_ratio + 1)),
        "stationary_zero": float(p["fs"]) / math.pi,
    }
    return case


def _lu_rbcot_esr(parameters: dict[str, Any], approximation: str) -> dict[str, Any]:
    p = _base_parameters(parameters)
    if float(p["rL"]) != 0:
        raise ModelError("Lu 2023 Eq. (10) assumes rL=0; set rL to zero for this model.")
    p.update(
        {
            "Toff": float(p["Tsw"]) - float(p["Ton"]),
            "sf": float(p["rC"]) * float(p["Vo"]) / float(p["L"]),
        }
    )
    if float(p["sf"]) <= 0:
        raise ModelError("Lu 2023 ESR-ripple model requires rC > 0.")
    if approximation == "exact":
        delay_id = "lu-2023.delay-exact"
        delay = bind_expression(delay_id)
        delay_origin = "paper-exponential"
    elif approximation == "pade":
        delay_id = "lu-2023.delay-pade"
        delay = bind_expression(delay_id)
        delay_origin = "paper-pade-after-Eq11"
    else:
        raise ModelError("Lu 2023 approximation must be 'exact' or 'pade'.")

    one_minus_delay = bind_expression("lu-2023.one-minus-delay", delay=delay)
    common_denominator = bind_expression("lu-2023.b", one_minus_delay=one_minus_delay)
    fdx = bind_expression(
        "lu-2023.fdx", one_minus_delay=one_minus_delay, B=common_denominator
    )
    fodx = bind_expression(
        "lu-2023.fodx", one_minus_delay=one_minus_delay, B=common_denominator
    )
    fox = bind_expression("lu-2023.fox", Fodx=fodx, Fdx=fdx)
    fp = bind_expression("lu-2023.fp")
    a_o = bind_expression("lu-2023.a-o", Fox=fox)
    modulator = {"a_c": fdx, "a_g": "0", "a_o": a_o, "a_i": "0"}
    return _paper_case(
        model_id="rbcot-esr-lu-2023",
        parameters=p,
        modulator=modulator,
        paper_model={
            "Fdx": fdx,
            "Fodx": fodx,
            "Fox": fox,
            "Fp": fp,
            "Floop_structure": bind_expression("lu-2023.floop"),
        },
        valid_frequency={
            "max_hz": float(p["fs"]) / 2,
            "basis": "Lu-2023-Pade-validation-to-fs-over-2",
        },
        coefficient_origin="paper-duty-df-with-sign-adapter",
        component_fidelity={
            "Fdx": "paper-equation-5",
            "Fodx": "paper-equation-8",
            "Fox": "paper-equation-9",
            "Fp": "paper-equation-10",
            "Floop": "paper-equation-11",
            "delay": delay_origin,
            "a_o": "derived-sign-adapter-from-Fox",
        },
        formula_bindings=[
            formula_binding(delay_id, delay),
            formula_binding("lu-2023.one-minus-delay", one_minus_delay, {"delay": delay}),
            formula_binding("lu-2023.b", common_denominator, {"one_minus_delay": one_minus_delay}),
            formula_binding("lu-2023.fdx", fdx, {"one_minus_delay": one_minus_delay, "B": common_denominator}),
            formula_binding("lu-2023.fodx", fodx, {"one_minus_delay": one_minus_delay, "B": common_denominator}),
            formula_binding("lu-2023.fox", fox, {"Fodx": fodx, "Fdx": fdx}),
            formula_binding("lu-2023.fp", fp),
            formula_binding("lu-2023.floop", bind_expression("lu-2023.floop")),
            formula_binding("lu-2023.a-o", a_o, {"Fox": fox}),
            formula_binding("common.zero.a-g", "0"),
            formula_binding("common.adapter.a-i", "0"),
        ],
    )


def _li_lee_2009_v2(parameters: dict[str, Any], approximation: str) -> dict[str, Any]:
    if approximation not in {"pade", "low-order"}:
        raise ModelError(
            "Li/Lee 2009 is bundled as the paper's simplified DF; "
            "use approximation='pade' or 'low-order'."
        )
    p = _base_parameters(parameters)
    p.update(
        {
            "w1": bind_expression("li-lee-2009.w1"),
            "Q1": bind_expression("li-lee-2009.q1"),
            "w2": bind_expression("li-lee-2009.w2"),
            "Q2": bind_expression("li-lee-2009.q2"),
        }
    )
    high_pair = bind_expression("li-lee-2009.high-pair")
    fs_pair = bind_expression("li-lee-2009.fs-pair")
    if approximation == "pade":
        gvc_id = "li-lee-2009.gvc-pade"
        gvc = bind_expression(gvc_id, high_pair=high_pair, fs_pair=fs_pair)
        basis = "Li-Lee-2009-Eq9"
    else:
        gvc_id = "li-lee-2009.gvc-low-order"
        gvc = bind_expression(gvc_id, fs_pair=fs_pair)
        basis = "Li-Lee-2009-Eq10"
    margin = float(p["rC"]) * float(p["C"]) - float(p["Ton"]) / 2
    case = _paper_case(
        model_id="v2-cot-li-lee-2009",
        parameters=p,
        modulator=None,
        paper_model={"Gvc": gvc},
        valid_frequency={"max_hz": float(p["fs"]) / 2, "basis": basis},
        coefficient_origin="not-applicable-direct-paper-transfer",
        component_fidelity={"Gvc": "paper-equation", "a_*": "not-claimed"},
        formula_bindings=[
            formula_binding("li-lee-2009.w1", p["w1"]),
            formula_binding("li-lee-2009.q1", p["Q1"]),
            formula_binding("li-lee-2009.w2", p["w2"]),
            formula_binding("li-lee-2009.q2", p["Q2"]),
            formula_binding("li-lee-2009.high-pair", high_pair),
            formula_binding("li-lee-2009.fs-pair", fs_pair),
            formula_binding(
                gvc_id,
                gvc,
                {"high_pair": high_pair, "fs_pair": fs_pair}
                if approximation == "pade" else {"fs_pair": fs_pair},
            ),
        ],
    )
    case.update(
        {
            "interface": "direct-transfer-function",
            "targets": ["Gvc"],
            "stability": {
                "criterion": "rC*C > Ton/2",
                "margin_seconds": margin,
                "stable_by_paper_boundary": margin > 0,
            },
        }
    )
    return case


def generate_case(model_id: str, parameters: dict[str, Any], approximation: str = "exact") -> dict[str, Any]:
    if model_id in EXCLUDED_MODELS:
        raise ModelError(EXCLUDED_MODELS[model_id])
    if model_id not in MODEL_SPECS:
        raise ModelError(
            f"Unknown model {model_id!r}. Supported models: {', '.join(list_models())}"
        )
    if model_id == "cot-cm-li-lee-2010":
        return _li_lee_2010(parameters, approximation)
    if model_id == "cot-cm-external-ramp-tian-2015":
        return _tian_external_ramp(parameters, approximation)
    if model_id == "rbcot-esr-lu-2023":
        return _lu_rbcot_esr(parameters, approximation)
    if model_id == "v2-cot-li-lee-2009":
        return _li_lee_2009_v2(parameters, approximation)
    raise ModelError(f"Model {model_id!r} is registered but not implemented.")
