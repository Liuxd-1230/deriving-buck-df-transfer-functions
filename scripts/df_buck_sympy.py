#!/usr/bin/env python3
"""Derive CCM buck transfer functions from user-supplied DF coefficients."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import sympy as sp
except Exception as exc:  # pragma: no cover - environment dependent
    print(
        "SymPy is required. Install it in the active Python environment "
        "(for example: python -m pip install sympy). "
        f"Import error: {exc}",
        file=sys.stderr,
    )
    raise SystemExit(2) from exc


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from df_model_library import (  # noqa: E402
    MODEL_SPECS,
    ModelError,
    generate_case,
    list_models,
)
from df_model_classifier import classify_intake  # noqa: E402
from df_protocol_case import (  # noqa: E402
    ProtocolCaseError,
    build_protocol_case,
    render_protocol_report,
)


IDENTIFIER = re.compile(r"\b[A-Za-z_]\w*\b")
KNOWN_FUNCTIONS = {
    "exp": sp.exp,
    "sqrt": sp.sqrt,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "log": sp.log,
    "pi": sp.pi,
    "I": sp.I,
}
BASE_SYMBOLS = ("s", "L", "C", "R", "rL", "rC", "Vg", "D")
SUPPORTED_TARGETS = {"Gvd", "Gvg_open", "Zout_open", "Gvc", "Gvg", "Zout", "Tloop"}


class CaseError(ValueError):
    """Raised when a case cannot be interpreted safely."""


def load_case(path: str | Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CaseError(f"Case file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CaseError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CaseError("The case root must be a JSON object.")
    return data


def _all_expression_text(case: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for section in ("parameters", "modulator", "feedback"):
        value = case.get(section, {})
        if isinstance(value, dict):
            texts.extend(str(v) for v in value.values())
    return texts


def build_symbol_table(case: dict[str, Any]) -> dict[str, Any]:
    names = set(BASE_SYMBOLS)
    names.update(str(k) for k in case.get("parameters", {}).keys())
    for text in _all_expression_text(case):
        names.update(IDENTIFIER.findall(text))
    names.difference_update(KNOWN_FUNCTIONS)
    table: dict[str, Any] = {name: sp.Symbol(name) for name in sorted(names)}
    table.update(KNOWN_FUNCTIONS)
    return table


def parse_expr(value: Any, table: dict[str, Any]) -> sp.Expr:
    if isinstance(value, bool):
        raise CaseError("Boolean values are not valid symbolic expressions.")
    try:
        return sp.sympify(value, locals=table)
    except Exception as exc:
        raise CaseError(f"Cannot parse expression {value!r}: {exc}") from exc


def validate_case(case: dict[str, Any]) -> dict[str, list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if case.get("topology", "buck-ccm") != "buck-ccm":
        errors.append("Only topology='buck-ccm' is supported.")
    if case.get("phases", 1) != 1:
        errors.append("This helper supports only a single phase; use a dedicated multiphase DF model.")

    mod = case.get("modulator")
    if not isinstance(mod, dict):
        errors.append("A modulator object with a_c/a_g/a_o/a_i is required.")
    else:
        for key in ("a_c", "a_g", "a_o", "a_i"):
            if key not in mod:
                errors.append(f"modulator.{key} is required (use '0' when absent).")

    targets = case.get("targets", ["Gvc", "Gvg", "Zout"])
    if not isinstance(targets, list) or not targets:
        errors.append("targets must be a non-empty list.")
    else:
        unknown = sorted(set(targets) - SUPPORTED_TARGETS)
        if unknown:
            errors.append(f"Unknown targets: {', '.join(unknown)}")
        if "Tloop" in targets and not isinstance(case.get("feedback"), dict):
            errors.append("Tloop requires feedback.Gc and feedback.H.")

    if not case.get("df_source"):
        warnings.append("df_source is missing; record the edge-condition derivation or literature source.")
    if not case.get("valid_frequency"):
        warnings.append("valid_frequency is missing; state the claimed model frequency range.")
    return {"errors": errors, "warnings": warnings}


def _resolved_substitutions(
    parameters: dict[str, Any], table: dict[str, Any]
) -> dict[sp.Symbol, sp.Expr]:
    substitutions = {
        table[str(name)]: parse_expr(value, table) for name, value in parameters.items()
    }
    for _ in range(len(substitutions) + 1):
        updated = {key: sp.simplify(value.subs(substitutions)) for key, value in substitutions.items()}
        if updated == substitutions:
            break
        substitutions = updated
    return substitutions


def _clean(expr: sp.Expr) -> sp.Expr:
    return sp.factor(sp.cancel(sp.together(expr)))


def derive_model(case: dict[str, Any]) -> dict[str, Any]:
    diagnostics = validate_case(case)
    if diagnostics["errors"]:
        raise CaseError("; ".join(diagnostics["errors"]))

    table = build_symbol_table(case)
    s, L, C, R, rL, rC, Vg, D = (table[name] for name in BASE_SYMBOLS)
    iL, vo, duty, uc, vg, iload = sp.symbols("iL vo duty uc vg iload")

    mod = case["modulator"]
    ac = parse_expr(mod["a_c"], table)
    ag = parse_expr(mod["a_g"], table)
    ao = parse_expr(mod["a_o"], table)
    ai = parse_expr(mod["a_i"], table)

    z_cap = rC + 1 / (s * C)
    y_parallel = 1 / R + 1 / z_cap
    z_parallel = _clean(1 / y_parallel)
    a_inductor = s * L + rL

    matrix = sp.Matrix(
        [
            [a_inductor, 1, -Vg],
            [1, -y_parallel, 0],
            [-ai, -ao, 1],
        ]
    )
    rhs = sp.Matrix([D * vg, iload, ac * uc + ag * vg])
    solution = matrix.LUsolve(rhs)
    i_expr, vo_expr, duty_expr = map(_clean, solution)

    gvd = _clean(Vg * z_parallel / (a_inductor + z_parallel))
    gvg_open = _clean(D * z_parallel / (a_inductor + z_parallel))
    zout_open = _clean(a_inductor * z_parallel / (a_inductor + z_parallel))

    expressions: dict[str, sp.Expr] = {
        "Gvd": gvd,
        "Gvg_open": gvg_open,
        "Zout_open": zout_open,
        "Gvc": _clean(sp.diff(vo_expr, uc)),
        "Gvg": _clean(sp.diff(vo_expr, vg)),
        "Zout": _clean(-sp.diff(vo_expr, iload)),
    }

    feedback = case.get("feedback")
    if isinstance(feedback, dict):
        if "Gc" not in feedback or "H" not in feedback:
            raise CaseError("feedback must contain both Gc and H.")
        gc = parse_expr(feedback["Gc"], table)
        h = parse_expr(feedback["H"], table)
        expressions["Tloop"] = _clean(gc * h * expressions["Gvc"])

    substitutions = _resolved_substitutions(case.get("parameters", {}), table)
    evaluated = {name: _clean(expr.subs(substitutions)) for name, expr in expressions.items()}

    return {
        "table": table,
        "symbols": {"s": s, "L": L, "C": C, "R": R, "rL": rL, "rC": rC, "Vg": Vg, "D": D},
        "modulator": {"a_c": ac, "a_g": ag, "a_o": ao, "a_i": ai},
        "matrix": matrix,
        "state_solution": {"iL": i_expr, "vo": vo_expr, "d": duty_expr},
        "expressions": expressions,
        "evaluated": evaluated,
        "substitutions": substitutions,
        "diagnostics": diagnostics,
    }


def _safe_limit(expr: sp.Expr, symbol: sp.Symbol, point: Any) -> str:
    try:
        result = _clean(sp.limit(expr, symbol, point))
        if not result.free_symbols and result.is_finite is not False:
            return str(sp.N(result, 10))
        return str(result)
    except Exception as exc:
        return f"unresolved ({type(exc).__name__}: {exc})"


def _numeric_poles(expr: sp.Expr, s: sp.Symbol) -> list[str] | None:
    numerator, denominator = sp.fraction(_clean(expr))
    del numerator
    if denominator.free_symbols - {s}:
        return None
    try:
        polynomial = sp.Poly(denominator, s)
        if polynomial.degree() < 1:
            return []
        return [str(complex(root)) for root in sp.nroots(polynomial)]
    except Exception:
        return None


def build_check_report(case: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    symbols = model["symbols"]
    s, L, C, R, rL, rC, Vg, D = (symbols[name] for name in BASE_SYMBOLS)
    expressions = model["expressions"]
    evaluated = model["evaluated"]

    dc_expected = {
        "Gvd": Vg * R / (R + rL),
        "Gvg_open": D * R / (R + rL),
        "Zout_open": rL * R / (R + rL),
    }
    structural = {}
    for name, expected in dc_expected.items():
        actual = sp.limit(expressions[name], s, 0)
        structural[f"{name}_dc_identity"] = sp.simplify(actual - expected) == 0

    targets = case.get("targets", ["Gvc", "Gvg", "Zout"])
    results = {}
    for name in targets:
        expr = evaluated[name]
        results[name] = {
            "expression": str(expr),
            "dc_limit": _safe_limit(expr, s, 0),
            "high_frequency_limit": _safe_limit(expr, s, sp.oo),
            "numeric_poles": _numeric_poles(expr, s),
            "remaining_symbols": sorted(str(symbol) for symbol in expr.free_symbols - {s}),
        }

    return {
        "case": case.get("name", "unnamed"),
        "diagnostics": model["diagnostics"],
        "structural_checks": structural,
        "results": results,
        "manual_checks_required": [
            "DF coefficients were derived from the correct switching-edge condition.",
            "Units and feedback signs are consistent.",
            "Low-frequency and special-case limits match an independent model.",
            "Literature benchmark is reproduced for a matching control law.",
            "Magnitude and phase agree with switching simulation over the claimed frequency range.",
        ],
    }


def _markdown(case: dict[str, Any], model: dict[str, Any], report: dict[str, Any]) -> str:
    targets = case.get("targets", ["Gvc", "Gvg", "Zout"])
    lines = [
        f"# {case.get('name', 'Buck DF derivation')}",
        "",
        "## Model declaration",
        "",
        f"- Topology: `{case.get('topology', 'buck-ccm')}`",
        f"- Phases: `{case.get('phases', 1)}`",
        f"- DF source: {case.get('df_source', 'NOT PROVIDED')}",
        f"- Claimed valid frequency: {case.get('valid_frequency', 'NOT PROVIDED')}",
        "",
        "## Modulator coefficients",
        "",
    ]
    for name, expr in model["modulator"].items():
        lines.append(f"- `${name}(s) = {sp.latex(expr)}$`")

    lines.extend(["", "## Transfer functions", ""])
    for name in targets:
        symbolic = model["expressions"][name]
        evaluated = model["evaluated"][name]
        lines.extend(
            [
                f"### {name}",
                "",
                f"Symbolic: `${sp.latex(symbolic)}$`",
                "",
                f"After parameter substitution: `${sp.latex(evaluated)}$`",
                "",
                f"DC limit: `{report['results'][name]['dc_limit']}`",
                "",
            ]
        )

    lines.extend(
        [
            "## Validation status",
            "",
            *[f"- [ ] {item}" for item in report["manual_checks_required"]],
            "",
            "Structural checks:",
            "",
            *[f"- {name}: `{value}`" for name, value in report["structural_checks"].items()],
            "",
            "> Algebraic consistency is not proof that the describing-function coefficients are physically correct.",
            "",
        ]
    )
    return "\n".join(lines)


def command_derive(args: argparse.Namespace) -> int:
    case = load_case(args.case)
    if str(case.get("case_version")) == "0.3":
        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_protocol_report(case), encoding="utf-8")
        print(f"Wrote protocol derivation: {output.resolve()}")
        return 0
    model = derive_model(case)
    report = build_check_report(case, model)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_markdown(case, model, report), encoding="utf-8")
    print(f"Wrote derivation: {output.resolve()}")
    if model["diagnostics"]["warnings"]:
        for warning in model["diagnostics"]["warnings"]:
            print(f"WARNING: {warning}", file=sys.stderr)
    return 0


def command_check(args: argparse.Namespace) -> int:
    case = load_case(args.case)
    model = derive_model(case)
    report = build_check_report(case, model)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    structural_ok = all(report["structural_checks"].values())
    return 0 if structural_ok and not report["diagnostics"]["errors"] else 1


def command_list_models(args: argparse.Namespace) -> int:
    model_ids = list_models()
    if args.json:
        print(json.dumps(model_ids, ensure_ascii=False, indent=2))
    else:
        for model_id in model_ids:
            spec = MODEL_SPECS[model_id]
            print(f"{model_id}\t{spec['method']}\t{spec['source']}")
    return 0


def command_make_case(args: argparse.Namespace) -> int:
    parameters = load_case(args.params)
    case = generate_case(args.model, parameters, args.approximation)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote generated case: {output.resolve()}")
    return 0


def command_classify(args: argparse.Namespace) -> int:
    intake = load_case(args.intake)
    print(json.dumps(classify_intake(intake), ensure_ascii=False, indent=2))
    return 0


def command_make_protocol_case(args: argparse.Namespace) -> int:
    intake = load_case(args.intake)
    case = build_protocol_case(intake)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote protocol case: {output.resolve()}")
    return 0


def command_benchmark(args: argparse.Namespace) -> int:
    from run_benchmarks import BENCHMARK_NAMES, run_benchmark

    names = BENCHMARK_NAMES if args.all else (args.benchmark,)
    output_root = Path(args.output_root) if args.output_root else SCRIPT_DIR.parent / "benchmarks"
    summary = {name: run_benchmark(name, output_root) for name in names}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Derive CCM buck transfer functions from describing-function coefficients."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    derive = subparsers.add_parser("derive", help="Write a Markdown derivation report.")
    derive.add_argument("--case", required=True, help="Input JSON case file.")
    derive.add_argument("--out", required=True, help="Output Markdown path.")
    derive.set_defaults(handler=command_derive)

    check = subparsers.add_parser("check", help="Print algebraic and limit checks as JSON.")
    check.add_argument("--case", required=True, help="Input JSON case file.")
    check.set_defaults(handler=command_check)

    list_command = subparsers.add_parser(
        "list-models", help="List paper-grounded DF model generators."
    )
    list_command.add_argument("--json", action="store_true", help="Emit a JSON list.")
    list_command.set_defaults(handler=command_list_models)

    make_case = subparsers.add_parser(
        "make-case", help="Generate a case from physical parameters and a paper model."
    )
    make_case.add_argument("--model", required=True, help="Registered paper model ID.")
    make_case.add_argument("--params", required=True, help="Physical-parameter JSON file.")
    make_case.add_argument("--out", required=True, help="Generated case JSON path.")
    make_case.add_argument(
        "--approximation",
        default="exact",
        help="Model-specific form such as exact, pade, or low-order.",
    )
    make_case.set_defaults(handler=command_make_case)

    classify = subparsers.add_parser(
        "classify", help="Classify circuit intake before selecting a DF path."
    )
    classify.add_argument("--intake", required=True, help="Circuit-intake JSON file.")
    classify.set_defaults(handler=command_classify)

    protocol_case = subparsers.add_parser(
        "make-protocol-case", help="Build an event-evidence case for a near or new model."
    )
    protocol_case.add_argument("--intake", required=True, help="Complete circuit-intake JSON file.")
    protocol_case.add_argument("--out", required=True, help="Protocol-case JSON path.")
    protocol_case.set_defaults(handler=command_make_protocol_case)

    benchmark = subparsers.add_parser(
        "benchmark", help="Generate bundled offline paper benchmarks."
    )
    benchmark_selection = benchmark.add_mutually_exclusive_group(required=True)
    benchmark_selection.add_argument("--all", action="store_true", help="Run all benchmarks.")
    benchmark_selection.add_argument(
        "--benchmark",
        choices=(
            "tian2015_external_ramp",
            "li_lee2010_cot_cm",
            "li_lee2009_v2_rbcot",
            "lu2023_rbcot_loopgain",
        ),
        help="Run one benchmark.",
    )
    benchmark.add_argument("--output-root", help="Optional benchmark output directory.")
    benchmark.set_defaults(handler=command_benchmark)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.handler(args)
    except (CaseError, ModelError, ProtocolCaseError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
