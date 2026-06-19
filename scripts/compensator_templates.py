#!/usr/bin/env python3
"""Canonical compensator templates for engineering Buck DF cases."""

from __future__ import annotations

from typing import Any


class CompensatorTemplateError(ValueError):
    """Raised when a compensator template is incomplete or ambiguous."""


def _require(data: dict[str, Any], names: tuple[str, ...]) -> None:
    missing = [name for name in names if data.get(name) in (None, "")]
    if missing:
        raise CompensatorTemplateError(f"Missing compensator fields: {', '.join(missing)}")


def _require_frequency_units(data: dict[str, Any]) -> None:
    if data.get("frequency_units") not in {"rad_per_s"}:
        raise CompensatorTemplateError("frequency_units='rad_per_s' is required for Type II/III templates.")


def _result(template_type: str, expression: str, parameters: dict[str, Any], **extra: Any) -> dict[str, Any]:
    result = {
        "type": template_type,
        "canonical_sympy_expr": expression,
        "parameters": parameters,
        "formula_origin": f"compensator-template:{template_type}",
    }
    result.update(extra)
    return result


def build_compensator(spec: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise CompensatorTemplateError("Compensator spec must be an object.")
    template_type = str(spec.get("type", "")).upper()
    if template_type == "SIMPLIS_LAPLACE":
        _require(spec, ("KPZ", "wz1", "wp1", "wp2"))
        form = spec.get("form", "simplicis_s_plus_w")
        if form != "simplicis_s_plus_w":
            raise CompensatorTemplateError("SIMPLIS_LAPLACE requires form='simplicis_s_plus_w'.")
        frequency_scale = spec.get("frequency_scale_factor", spec.get("F", 1))
        parameters = {
            "KPZ": spec["KPZ"],
            "wz1": spec["wz1"],
            "wp1": spec["wp1"],
            "wp2": spec["wp2"],
            "F": frequency_scale,
        }
        dc_gain = (
            float(spec["KPZ"]) * float(frequency_scale) * float(spec["wz1"])
            / (float(frequency_scale) * float(spec["wp1"]) * float(frequency_scale) * float(spec["wp2"]))
        )
        return _result(
            template_type,
            "KPZ*(s+F*wz1)/((s+F*wp1)*(s+F*wp2))",
            parameters,
            dc_gain=dc_gain,
            form=form,
        )
    if template_type == "OTA_GM_RO":
        _require(spec, ("gm", "Ro"))
        parameters = {"gm": spec["gm"], "Ro": spec["Ro"]}
        if spec.get("Cea") in (None, ""):
            return _result(template_type, "gm*Ro", parameters)
        parameters["Cea"] = spec["Cea"]
        return _result(template_type, "gm/(1/Ro+s*Cea)", parameters)
    if template_type == "PI":
        _require(spec, ("Kp", "wz"))
        if spec.get("parameterization", "zero_over_s") not in {"zero_over_s", "s_plus_wz_over_s"}:
            raise CompensatorTemplateError("PI parameterization must be zero_over_s or s_plus_wz_over_s.")
        return _result(
            template_type,
            "Kp*(s+wz)/s",
            {"Kp": spec["Kp"], "wz": spec["wz"], "parameterization": spec.get("parameterization", "zero_over_s")},
        )
    if template_type == "TYPE_II":
        _require(spec, ("K", "wz1", "wp1"))
        _require_frequency_units(spec)
        return _result(
            template_type,
            "K*(1+s/wz1)/(s*(1+s/wp1))",
            {"K": spec["K"], "wz1": spec["wz1"], "wp1": spec["wp1"], "frequency_units": spec["frequency_units"]},
        )
    if template_type == "TYPE_III":
        _require(spec, ("K", "wz1", "wz2", "wp1", "wp2"))
        _require_frequency_units(spec)
        return _result(
            template_type,
            "K*(1+s/wz1)*(1+s/wz2)/(s*(1+s/wp1)*(1+s/wp2))",
            {
                "K": spec["K"], "wz1": spec["wz1"], "wz2": spec["wz2"],
                "wp1": spec["wp1"], "wp2": spec["wp2"], "frequency_units": spec["frequency_units"],
            },
        )
    if template_type == "CUSTOM_EXPRESSION":
        _require(spec, ("expression",))
        return _result(
            template_type,
            str(spec["expression"]),
            dict(spec.get("parameters", {})),
            validation_level="CUSTOM_EXPRESSION_UNVERIFIED",
        )
    raise CompensatorTemplateError(f"Unsupported compensator template: {spec.get('type')!r}")
