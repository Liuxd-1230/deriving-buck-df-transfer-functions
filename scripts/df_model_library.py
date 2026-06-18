#!/usr/bin/env python3
"""Paper-grounded model registry for single-phase Buck DF models."""

from __future__ import annotations

import math
from typing import Any


class ModelError(ValueError):
    """Raised when a requested paper model is unsupported or invalid."""


MODEL_SPECS = {
    "cot-cm-li-lee-2010": {
        "method": "describing-function",
        "source": "Li and Lee, IEEE TPEL 2010",
    },
    "cot-cm-external-ramp-tian-2015": {
        "method": "describing-function",
        "source": "Tian et al., IEEE TPEL 2016 (early access 2015)",
    },
    "rbcot-esr-lu-2023": {
        "method": "describing-function",
        "source": "Lu et al., IEEE TPEL 2023",
    },
    "v2-cot-li-lee-2009": {
        "method": "describing-function",
        "source": "Li and Lee, IEEE ECCE 2009",
    },
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
        "a_c": f"(s*L+rL)*({Fc})/Vg",
        "a_g": f"((s*L+rL)*({Fg})-D)/Vg",
        "a_o": f"((s*L+rL)*({Fo})+1)/Vg",
        "a_i": "0",
        "coefficient_origin": "derived-adapter",
    }


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
        "targets": ["Gvc", "Gvg", "Zout"],
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
        fc = "(fs/sf)*(1-exp(-s*Ton))*Vg/(L*s)"
        basis = "Li-Lee-2010-Eq9"
    elif approximation == "pade":
        fc = "1/(Ri*(1+s/(Q1*w1)+s**2/w1**2))"
        basis = "Li-Lee-2010-Eq10"
    else:
        raise ModelError("Li/Lee 2010 approximation must be 'exact' or 'pade'.")

    k1 = "Ton*Ri/(2*L)"
    k2 = "-Ton*Ri/(2*L)"
    fg = f"({k1})*({fc})"
    fo = f"({k2})*({fc})"
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

    denominator = "((sf+se)-se*exp(-s*Tsw))"
    fc = f"fs*(1-exp(-s*Ton))*Vg/(L*s*{denominator})"
    fg = (
        "-1/(L*s)*("
        "fs*(1-exp(-s*Ton))/((1-exp(s*Tsw))*"
        f"{denominator})*((1-exp(s*Ton))/(s*L/Ri))*Vg+D)"
    )
    fo = (
        "1/(L*s)*("
        f"fs*(1-exp(-s*Ton))/{denominator}*(1/(s*L/Ri))*Vg-1)"
    )
    fc_low = "(1/Ri)*(1+s*Tsw/2)/(1+(se/sf+1/2)*Tsw*s)"
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
        delay = "exp(-s*Tsw)"
        delay_origin = "paper-exponential"
    elif approximation == "pade":
        delay = "(1-s*Tsw/(1+s*Tsw/2+s**2*Tsw**2/pi**2))"
        delay_origin = "paper-pade-after-Eq11"
    else:
        raise ModelError("Lu 2023 approximation must be 'exact' or 'pade'.")

    one_minus_delay = f"(1-({delay}))"
    common_denominator = (
        "(Tsw/(rC*C)+(1+(Toff-2*Tsw)/(2*rC*C))*"
        f"{one_minus_delay})"
    )
    fdx = (
        "(fs/sf)*(1-exp(-s*Ton))*"
        f"{one_minus_delay}*(1+rC/R)/{common_denominator}"
    )
    fodx = (
        "(fs/sf)*(1-exp(-s*Ton))*"
        f"{one_minus_delay}*(1/(s**2*L*C)+(rC/L+1/(R*C))/s)"
        f"/{common_denominator}"
    )
    fox = f"-({fodx})-({fdx})"
    fp = (
        "Vg*(1+s*rC*C)/"
        "(1+s*(rC*C+L/R)+s**2*L*C*(1+rC/R))"
    )
    modulator = {"a_c": fdx, "a_g": "0", "a_o": f"-({fox})", "a_i": "0"}
    return _paper_case(
        model_id="rbcot-esr-lu-2023",
        parameters=p,
        modulator=modulator,
        paper_model={
            "Fdx": fdx,
            "Fodx": fodx,
            "Fox": fox,
            "Fp": fp,
            "Floop_structure": "Fdx*Fp/(1+Fox*Fp)",
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
            "w1": "pi/Ton",
            "Q1": "2/pi",
            "w2": "pi/Tsw",
            "Q2": "Tsw/(pi*(rC*C-Ton/2))",
        }
    )
    high_pair = "(1+s/(Q1*w1)+s**2/w1**2)"
    fs_pair = "(1+s/(Q2*w2)+s**2/w2**2)"
    if approximation == "pade":
        gvc = f"(1+s*rC*C)/({high_pair}*{fs_pair})"
        basis = "Li-Lee-2009-Eq9"
    else:
        gvc = f"(1+s*rC*C)/{fs_pair}"
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
