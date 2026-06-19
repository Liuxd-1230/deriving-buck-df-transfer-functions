#!/usr/bin/env python3
"""Derive CCM buck transfer functions from user-supplied DF coefficients."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sp: Any = None


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from df_model_library import (  # noqa: E402
    MODEL_SPECS,
    ModelError,
    generate_case,
    list_models,
)
from df_model_classifier import classify_intake_status  # noqa: E402
from df_protocol_case import (  # noqa: E402
    ProtocolCaseError,
    build_protocol_case,
    render_protocol_report,
)
from build_proof_object import ProofBuildError, build_proof_object  # noqa: E402
from check_proof_object import check_proof_object  # noqa: E402
from preflight_intake import IntakeGateError, build_intake_status  # noqa: E402


IDENTIFIER = re.compile(r"\b[A-Za-z_]\w*\b")
BASE_SYMBOLS = ("s", "L", "C", "R", "rL", "rC", "Vg", "D")
SUPPORTED_TARGETS = {"Gvd", "Gvg_open", "Zout_open", "Gvc", "Gvg", "Zout", "Tloop"}


class CaseError(ValueError):
    """Raised when a case cannot be interpreted safely."""


def _require_sympy() -> Any:
    """Import SymPy only for commands that perform symbolic algebra."""

    global sp
    if sp is not None:
        return sp
    try:
        import sympy as sympy_module
    except Exception as exc:  # pragma: no cover - environment dependent
        raise CaseError(
            "SymPy is required for algebra, checks, and benchmarks. Install it in the "
            "active Python environment (for example: python -m pip install sympy). "
            f"Import error: {exc}"
        ) from exc
    sp = sympy_module
    return sp


def _known_functions() -> dict[str, Any]:
    sympy = _require_sympy()
    return {
        "exp": sympy.exp,
        "sqrt": sympy.sqrt,
        "sin": sympy.sin,
        "cos": sympy.cos,
        "tan": sympy.tan,
        "log": sympy.log,
        "pi": sympy.pi,
        "I": sympy.I,
    }


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
    sympy = _require_sympy()
    known_functions = _known_functions()
    names = set(BASE_SYMBOLS)
    names.update(str(k) for k in case.get("parameters", {}).keys())
    for text in _all_expression_text(case):
        names.update(IDENTIFIER.findall(text))
    names.difference_update(known_functions)
    table: dict[str, Any] = {name: sympy.Symbol(name) for name in sorted(names)}
    table.update(known_functions)
    return table


def parse_expr(value: Any, table: dict[str, Any]) -> sp.Expr:
    sympy = _require_sympy()
    if isinstance(value, bool):
        raise CaseError("Boolean values are not valid symbolic expressions.")
    try:
        return sympy.sympify(value, locals=table)
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
    _require_sympy()
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


def _render_proof_report(proof: dict[str, Any]) -> str:
    classification = proof["classification"]
    modulator = proof["modulator"]
    transfer = proof["transfer"]
    validation = proof["validation"]
    lines = [
        "# ESSF v0.3.1 proof report", "",
        "## Structured evidence", "",
        f"- Case: `{proof['case_id']}`",
        f"- Path: `{classification['path']}`",
        f"- Model: `{classification.get('model_id')}`",
        f"- Modulator interface: `{modulator['model_type']}`", "",
        "## Formula bindings", "",
    ]
    for binding in proof.get("formula_bindings", []):
        lines.append(f"- `{binding['formula_id']}`: `{binding['expression']}`")
    if modulator["model_type"] == "a-star":
        lines.extend(["", "## Mapping to a_c/a_g/a_o/a_i", ""])
        for name, binding in modulator["coefficients"].items():
            lines.append(f"- `{name}` from `{binding['formula_id']}`: `{binding['expression']}`")
    elif modulator["model_type"] == "protocol-derived":
        lines.extend(["", "## Protocol-derived relation", "", str(modulator.get("relation", {}))])
    lines.extend([
        "", "## Transfer", "",
        f"- Target: `{transfer['target_transfer']}`",
        f"- Formula ID: `{transfer.get('formula_id')}`",
        f"- Expression: `{transfer['expression']}`", "",
        "## Validation", "",
        f"- Level: `{validation['level']}`",
        f"- Completed: {validation['completed']}",
        f"- Missing: {validation['missing']}", "",
        "> Markdown is display only. The checked proof object and formula registry are authoritative.", "",
    ])
    return "\n".join(lines)


def command_derive(args: argparse.Namespace) -> int:
    if not args.proof_object:
        raise CaseError(
            "Final report generation requires a checked v0.3.1 proof object; "
            "legacy --case remains available only to the algebraic check command."
        )
    proof = load_case(args.proof_object)
    result = check_proof_object(proof)
    if result["status"] != "PASS":
        raise CaseError(f"Proof object rejected: {result['status']}: {'; '.join(result['errors'])}")
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_render_proof_report(proof), encoding="utf-8")
    print(f"Wrote ESSF proof report: {output.resolve()}")
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
    artifact = load_case(args.intake_status)
    classification = classify_intake_status(artifact)
    if args.out:
        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(classification, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(classification, ensure_ascii=False, indent=2))
    return 0


def command_make_protocol_case(args: argparse.Namespace) -> int:
    intake = load_case(args.intake)
    build_protocol_case(intake)  # compatibility validation; output is now a proof object
    intake_status = build_intake_status(intake=intake)
    classification = classify_intake_status(intake_status)
    case = build_proof_object(intake_status, classification)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote protocol case: {output.resolve()}")
    return 0


def command_benchmark(args: argparse.Namespace) -> int:
    _require_sympy()
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
    derive_input = derive.add_mutually_exclusive_group(required=True)
    derive_input.add_argument("--case", help="Legacy v0.2 generated case file.")
    derive_input.add_argument("--proof-object", help="Checked ESSF v0.3.1 proof object.")
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
    classify.add_argument("--intake-status", required=True, help="Completed intake_status.json artifact.")
    classify.add_argument("--out", help="Optional classification.json output path.")
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
    except (CaseError, ModelError, ProtocolCaseError, IntakeGateError, ProofBuildError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
