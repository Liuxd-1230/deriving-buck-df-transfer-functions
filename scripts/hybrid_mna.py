#!/usr/bin/env python3
"""Circuit-IR-derived Hybrid MNA/DAE construction for the v0.5 physics path."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import signal

from circuit_ir import circuit_content_hash, validate_circuit_ir
from physics_workflow import attach_physics_workflow, content_hash, verify_physics_workflow
from schema_validation import validate_artifact


class HybridMNAError(ValueError):
    """Raised when confirmed circuit structure cannot produce an index-1 mode DAE."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass
class Allocation:
    variables: list[str]
    nodes: dict[str, int]
    branches: dict[str, int]
    internal_states: dict[str, list[int]]


BRANCH_TYPES = {"voltage_source", "vcvs", "inductor", "ideal_switch", "diode", "ramp", "lti_block"}
IGNORED_MNA_TYPES = {"comparator"}
VOLTAGE_CONSTRAINT_TYPES = {"voltage_source", "vcvs", "ramp", "lti_block"}


def _number(value: Any, *, field: str) -> float:
    if isinstance(value, dict):
        value = value.get("magnitude")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise HybridMNAError("FAIL_NUMERIC_PARAMETER_REQUIRED", field) from exc
    if not np.isfinite(result):
        raise HybridMNAError("FAIL_NONFINITE_PARAMETER", field)
    return result


def physics_spec_content_hash(spec: dict[str, Any]) -> str:
    return content_hash(spec, "confirmation")


def validate_physics_spec(spec: dict[str, Any], circuit_ir: dict[str, Any]) -> None:
    validate_artifact(spec, "physics_spec.schema.json")
    verify_physics_workflow(spec, expected_state="PHYSICS_SPEC_CONFIRMED", predecessor=circuit_ir)
    circuit_errors = validate_circuit_ir(circuit_ir, require_confirmation=True)
    if circuit_errors:
        raise HybridMNAError("FAIL_CIRCUIT_IR", "; ".join(circuit_errors))
    if spec["circuit_ir_sha256"] != circuit_ir["workflow"]["artifact_sha256"]:
        raise HybridMNAError("FAIL_CIRCUIT_IR_HASH_MISMATCH", "physics spec does not bind confirmed Circuit IR")
    if spec["confirmation"]["confirmed_content_sha256"] != physics_spec_content_hash(spec):
        raise HybridMNAError("FAIL_PHYSICS_SPEC_CONFIRMATION_HASH", "confirmed content hash mismatch")
    if spec["case_id"] != circuit_ir["case_id"]:
        raise HybridMNAError("FAIL_CASE_ID_MISMATCH", "Circuit IR and Physics Spec case IDs differ")
    target = spec["target"]
    ports = circuit_ir.get("ports", [])
    port_names = {port["name"] for port in ports}
    if len(port_names) != len(ports):
        raise HybridMNAError("FAIL_DUPLICATE_PORT", "Circuit IR port names must be unique")
    if target["input"] not in port_names or target["output"] not in port_names:
        raise HybridMNAError("FAIL_TARGET_PORT_NOT_DECLARED", f"{target['input']}->{target['output']}")
    if target["input"] not in spec["inputs"]:
        raise HybridMNAError("ASK_USER_ONLY:TARGET_INPUT_VALUE", target["input"])
    if target["name"] == "Zout" and "scale" not in target:
        raise HybridMNAError(
            "ASK_USER_ONLY:ZOUT_DISTURBANCE_SIGN",
            "declare target.scale from the confirmed load-current reference direction",
        )
    if target["name"] == "Tloop" and not spec.get("loop_break"):
        raise HybridMNAError("FAIL_TLOOP_REQUIRES_LOOP_BREAK", "Tloop requires explicit loop_break")
    if target["name"] == "Tloop":
        if target["response_kind"] != "return_ratio":
            raise HybridMNAError("FAIL_TLOOP_RESPONSE_KIND", "Tloop must be a return_ratio")
        required_loop_break = {
            "injection_point", "out_definition", "in_definition", "sign_convention",
            "forward_path", "feedback_path", "H",
        }
        missing = sorted(required_loop_break - set(spec["loop_break"]))
        if missing:
            raise HybridMNAError("ASK_USER_ONLY:LOOP_BREAK_SEMANTICS", ",".join(missing))
    mode_ids = {mode["id"] for mode in spec["modes"]}
    if len(mode_ids) != len(spec["modes"]):
        raise HybridMNAError("FAIL_DUPLICATE_MODE_ID", "mode IDs must be unique")
    if any(item["mode"] not in mode_ids for item in spec["mode_sequence"]):
        raise HybridMNAError("FAIL_MODE_SEQUENCE_UNKNOWN_MODE", "mode_sequence references an unknown mode")
    if spec["poincare_section"]["mode"] != spec["mode_sequence"][0]["mode"]:
        raise HybridMNAError("FAIL_POINCARE_SECTION_SEQUENCE", "section mode must be the first interval after turn-on")
    section = spec["poincare_section"]
    if section.get("definition") == "period_start_after_turn_on":
        ground = circuit_ir["ground_net"]
        source_nets = {
            item["terminals"]["p"] for item in circuit_ir["components"]
            if item["type"] == "voltage_source" and item["terminals"].get("n") == ground
            and (item.get("parameters") or {}).get("input") == "vg"
        }
        high_devices = {
            item["id"] for item in circuit_ir["components"]
            if item["type"] in {"ideal_switch", "diode"}
            and any(net in item["terminals"].values() for net in source_nets)
        }
        first_mode = next(item for item in spec["modes"] if item["id"] == spec["mode_sequence"][0]["mode"])
        if high_devices and not any(first_mode["switch_states"].get(cid) == "ON" for cid in high_devices):
            raise HybridMNAError("FAIL_EVENT_MODE_ORDER", "default Poincare section must begin immediately after high-side turn-on")
    elif not section.get("notes"):
        raise HybridMNAError("ASK_USER_ONLY:CUSTOM_POINCARE_SECTION", "custom section requires notes")
    for index, entry in enumerate(spec["mode_sequence"]):
        termination = entry["termination"]
        if termination["type"] == "fixed_duration" and "duration" not in termination:
            raise HybridMNAError("ASK_USER_ONLY:FIXED_EVENT_DURATION", str(index))
        if termination["type"] == "guard":
            if not termination.get("expression") or "direction" not in termination:
                raise HybridMNAError("ASK_USER_ONLY:GUARD_SEMANTICS", str(index))
            if "max_duration" not in termination:
                raise HybridMNAError("ASK_USER_ONLY:GUARD_SEARCH_WINDOW", str(index))
    declared_guards = {
        str((component.get("parameters") or {}).get("guard_expression"))
        for component in circuit_ir.get("components", []) if component.get("type") == "comparator"
    }
    sequence_guards = {
        str(entry["termination"].get("expression")) for entry in spec["mode_sequence"]
        if entry["termination"]["type"] == "guard"
    }
    if sequence_guards and not sequence_guards.issubset(declared_guards):
        raise HybridMNAError("FAIL_COMPARATOR_GUARD_MISMATCH", f"spec={sequence_guards}, circuit={declared_guards}")
    source_inputs = {
        (component.get("parameters") or {}).get("input")
        for component in circuit_ir.get("components", [])
        if component.get("type") in {"voltage_source", "current_source"}
        and (component.get("parameters") or {}).get("input") is not None
    }
    missing_inputs = sorted(str(name) for name in source_inputs if name not in spec["inputs"])
    if missing_inputs:
        raise HybridMNAError("ASK_USER_ONLY:SOURCE_INPUT_VALUE", ",".join(missing_inputs))
    loop_break = spec.get("loop_break") or {}
    feedback_paths = loop_break.get("feedback_paths")
    if isinstance(feedback_paths, list) and len(feedback_paths) != 1:
        raise HybridMNAError("FAIL_DUPLICATE_FEEDBACK_PATH", "exactly one active feedback path is required")


def _allocate(
    circuit_ir: dict[str, Any], components: list[dict[str, Any]] | None = None
) -> Allocation:
    ground = circuit_ir["ground_net"]
    components = circuit_ir["components"] if components is None else components
    variables: list[str] = []
    nodes: dict[str, int] = {}
    for net in circuit_ir["nets"]:
        net_id = str(net["id"])
        if net_id == ground:
            continue
        nodes[net_id] = len(variables)
        variables.append(f"v_{net_id}")
    branches: dict[str, int] = {}
    for component in components:
        if component["type"] in BRANCH_TYPES:
            branches[component["id"]] = len(variables)
            variables.append(f"i_{component['id']}")
    internal_states: dict[str, list[int]] = {}
    for component in components:
        count = 0
        if component["type"] in {"ramp", "timer"}:
            count = 1
        elif component["type"] == "lti_block":
            matrix = (component.get("parameters") or {}).get("A")
            count = len(matrix) if isinstance(matrix, list) else 0
            if count < 1:
                raise HybridMNAError("FAIL_LTI_STATE_SPACE", f"{component['id']} lacks A matrix")
        if count:
            indices = []
            for index in range(count):
                indices.append(len(variables))
                variables.append(f"x_{component['id']}_{index}")
            internal_states[component["id"]] = indices
    return Allocation(variables, nodes, branches, internal_states)


def _realize_lti_blocks(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    realized = copy.deepcopy(components)
    for component in realized:
        if component.get("type") != "lti_block":
            continue
        parameters = component.setdefault("parameters", {})
        has_state_space = all(name in parameters for name in ("A", "B", "C", "D"))
        has_transfer = all(name in parameters for name in ("numerator", "denominator"))
        if not has_state_space and not has_transfer:
            raise HybridMNAError(
                "FAIL_LTI_REALIZATION_REQUIRED",
                f"{component['id']} requires A/B/C/D or numerator/denominator",
            )
        if has_transfer and not has_state_space:
            numerator = np.asarray(parameters["numerator"], dtype=float)
            denominator = np.asarray(parameters["denominator"], dtype=float)
            if numerator.ndim != 1 or denominator.ndim != 1 or not numerator.size or denominator.size < 2:
                raise HybridMNAError("FAIL_LTI_RATIONAL_FORM", str(component["id"]))
            if not np.isfinite(numerator).all() or not np.isfinite(denominator).all() or denominator[0] == 0:
                raise HybridMNAError("FAIL_LTI_RATIONAL_FORM", str(component["id"]))
            try:
                Am, Bm, Cm, Dm = signal.tf2ss(numerator, denominator)
            except (ValueError, np.linalg.LinAlgError) as exc:
                raise HybridMNAError("FAIL_LTI_RATIONAL_FORM", str(component["id"])) from exc
            parameters.update({
                "A": Am.tolist(), "B": Bm.tolist(), "C": Cm.tolist(), "D": Dm.tolist(),
                "realization_source": "rational_transfer_function",
            })
        else:
            parameters.setdefault("realization_source", "declared_state_space")
        Am = np.asarray(parameters["A"], dtype=float)
        Bm = np.asarray(parameters["B"], dtype=float)
        Cm = np.asarray(parameters["C"], dtype=float)
        Dm = np.asarray(parameters["D"], dtype=float)
        state_count = Am.shape[0] if Am.ndim == 2 else 0
        if (
            state_count < 1 or Am.shape != (state_count, state_count)
            or Bm.shape != (state_count, 1) or Cm.shape != (1, state_count)
            or Dm.shape != (1, 1) or not all(np.isfinite(matrix).all() for matrix in (Am, Bm, Cm, Dm))
        ):
            raise HybridMNAError("FAIL_LTI_SISO_STATE_SPACE", str(component["id"]))
    return realized


def _check_voltage_constraint_loops(
    components: list[dict[str, Any]], mode: dict[str, Any]
) -> None:
    """Reject cycles of ideal voltage constraints before descriptor reduction."""
    parent: dict[str, str] = {}
    edge_components: dict[frozenset[str], list[str]] = {}

    def find(net: str) -> str:
        parent.setdefault(net, net)
        while parent[net] != net:
            parent[net] = parent[parent[net]]
            net = parent[net]
        return net

    def union(left: str, right: str) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for component in components:
        kind = component["type"]
        is_constraint = kind in VOLTAGE_CONSTRAINT_TYPES
        if kind in {"ideal_switch", "diode"}:
            is_constraint = (mode.get("switch_states") or {}).get(component["id"]) == "ON"
        if not is_constraint:
            continue
        terminals = component.get("terminals") or {}
        if "p" not in terminals or "n" not in terminals:
            continue
        left, right = str(terminals["p"]), str(terminals["n"])
        key = frozenset((left, right))
        if left == right or find(left) == find(right):
            involved = edge_components.get(key, []) + [str(component["id"])]
            raise HybridMNAError(
                "FAIL_IDEAL_VOLTAGE_SOURCE_LOOP",
                f"mode={mode['id']}; closing_component={component['id']}; parallel_or_cycle={involved}",
            )
        edge_components.setdefault(key, []).append(str(component["id"]))
        union(left, right)


def _idx(nodes: dict[str, int], ground: str, net: str) -> int | None:
    return None if net == ground else nodes[net]


def _add(matrix: np.ndarray, row: int | None, col: int | None, value: float) -> None:
    if row is not None and col is not None:
        matrix[row, col] += value


def _stamp_two_terminal(matrix: np.ndarray, p: int | None, n: int | None, value: float) -> None:
    _add(matrix, p, p, value)
    _add(matrix, p, n, -value)
    _add(matrix, n, p, -value)
    _add(matrix, n, n, value)


def _branch_kcl(A: np.ndarray, p: int | None, n: int | None, branch: int) -> None:
    _add(A, p, branch, -1.0)
    _add(A, n, branch, 1.0)


def _terminal_pair(component: dict[str, Any], nodes: dict[str, int], ground: str, p_name: str = "p", n_name: str = "n") -> tuple[int | None, int | None]:
    terminals = component.get("terminals") or {}
    if p_name not in terminals or n_name not in terminals:
        raise HybridMNAError("FAIL_COMPONENT_TERMINALS", f"{component['id']} requires {p_name}/{n_name}")
    return _idx(nodes, ground, terminals[p_name]), _idx(nodes, ground, terminals[n_name])


def _input_index(input_names: list[str], name: Any, component_id: str) -> int:
    if name not in input_names:
        raise HybridMNAError("FAIL_SOURCE_INPUT_NOT_DECLARED", f"{component_id}:{name}")
    return input_names.index(str(name))


def _stamp_component(
    component: dict[str, Any], mode: dict[str, Any], allocation: Allocation,
    input_names: list[str], ground: str, E: np.ndarray, A: np.ndarray,
    B: np.ndarray, b: np.ndarray, equations: list[dict[str, Any]],
    provenance: list[dict[str, Any]], energy_states: list[dict[str, Any]],
) -> None:
    kind = component["type"]
    cid = component["id"]
    if kind in IGNORED_MNA_TYPES:
        provenance.append({"component_id": cid, "role": "event_semantics", "mode": mode["id"]})
        return
    if kind == "timer":
        state = allocation.internal_states[cid][0]
        E[state, state] = 1.0
        active_modes = params = component.get("parameters") or {}
        selected = params.get("active_modes")
        rate = _number(params.get("rate", 1.0), field=f"{cid}.rate")
        if isinstance(selected, list) and mode["id"] not in selected:
            rate = 0.0
        b[state] += rate
        equations.append({
            "id": f"law_{cid}", "kind": "timer_state",
            "text": f"d(x_{cid})/dt={rate}", "component_id": cid,
        })
        provenance.append({"component_id": cid, "component_type": kind, "mode": mode["id"], "source": "confirmed-circuit-ir"})
        return
    p, n = _terminal_pair(component, allocation.nodes, ground)
    params = component.get("parameters") or {}
    if kind == "resistor":
        resistance = _number(component.get("value"), field=f"{cid}.value")
        if resistance <= 0:
            raise HybridMNAError("FAIL_PASSIVE_VALUE", f"{cid} resistance must be positive")
        _stamp_two_terminal(A, p, n, -1.0 / resistance)
        equations.append({"id": f"law_{cid}", "kind": "constitutive", "text": f"v({cid})={resistance}*i({cid})", "component_id": cid})
    elif kind == "capacitor":
        capacitance = _number(component.get("value"), field=f"{cid}.value")
        if capacitance <= 0:
            raise HybridMNAError("FAIL_PASSIVE_VALUE", f"{cid} capacitance must be positive")
        _stamp_two_terminal(E, p, n, capacitance)
        energy_states.append({
            "component_id": cid, "kind": "electric", "expression": "0.5*C*v**2",
            "value": capacitance, "terminals": copy.deepcopy(component["terminals"]),
            "voltage_expression": f"v_{component['terminals']['p']}-v_{component['terminals']['n']}",
        })
        equations.append({"id": f"law_{cid}", "kind": "constitutive", "text": f"i({cid})={capacitance}*d(v({cid}))/dt", "component_id": cid})
    elif kind == "inductor":
        inductance = _number(component.get("value"), field=f"{cid}.value")
        if inductance <= 0:
            raise HybridMNAError("FAIL_PASSIVE_VALUE", f"{cid} inductance must be positive")
        branch = allocation.branches[cid]
        _branch_kcl(A, p, n, branch)
        E[branch, branch] += inductance
        _add(A, branch, p, 1.0)
        _add(A, branch, n, -1.0)
        resistance = _number(params.get("series_resistance", 0.0), field=f"{cid}.series_resistance")
        A[branch, branch] -= resistance
        energy_states.append({
            "component_id": cid, "variable": f"i_{cid}", "kind": "magnetic",
            "expression": "0.5*L*i**2", "value": inductance,
            "series_resistance": resistance, "terminals": copy.deepcopy(component["terminals"]),
        })
        equations.append({"id": f"law_{cid}", "kind": "KVL", "text": f"L*d(i_{cid})/dt=v_p-v_n-{resistance}*i_{cid}", "component_id": cid})
    elif kind in {"voltage_source", "current_source"}:
        dc_source = params["dc"] if "dc" in params else component.get("value", 0.0)
        dc = _number(dc_source, field=f"{cid}.dc")
        gain = _number(params.get("gain", 1.0), field=f"{cid}.gain")
        input_name = params.get("input")
        if kind == "voltage_source":
            branch = allocation.branches[cid]
            _branch_kcl(A, p, n, branch)
            _add(A, branch, p, 1.0)
            _add(A, branch, n, -1.0)
            b[branch] -= dc
            if input_name is not None:
                B[branch, _input_index(input_names, input_name, cid)] -= gain
            equations.append({"id": f"law_{cid}", "kind": "source", "text": f"v_p-v_n={dc}+{gain}*{input_name or 0}", "component_id": cid})
        else:
            if p is not None:
                b[p] -= dc
            if n is not None:
                b[n] += dc
            if input_name is not None:
                column = _input_index(input_names, input_name, cid)
                if p is not None:
                    B[p, column] -= gain
                if n is not None:
                    B[n, column] += gain
            equations.append({"id": f"law_{cid}", "kind": "source", "text": f"i_p_to_n={dc}+{gain}*{input_name or 0}", "component_id": cid})
    elif kind in {"ideal_switch", "diode"}:
        branch = allocation.branches[cid]
        _branch_kcl(A, p, n, branch)
        state = (mode.get("switch_states") or {}).get(cid)
        if state not in {"ON", "OFF"}:
            raise HybridMNAError("FAIL_SWITCH_STATE_MISSING", f"{mode['id']}:{cid}")
        if state == "ON":
            _add(A, branch, p, 1.0)
            _add(A, branch, n, -1.0)
            law = "v_p-v_n=0"
        else:
            A[branch, branch] += 1.0
            law = f"i_{cid}=0"
        equations.append({"id": f"law_{cid}", "kind": "switch_constraint", "text": law, "component_id": cid, "state": state})
    elif kind == "vccs":
        cp, cn = _terminal_pair(component, allocation.nodes, ground, "cp", "cn")
        gain = _number(params.get("gain"), field=f"{cid}.gain")
        _add(A, p, cp, -gain); _add(A, p, cn, gain)
        _add(A, n, cp, gain); _add(A, n, cn, -gain)
        equations.append({"id": f"law_{cid}", "kind": "controlled_source", "text": f"i={gain}*(v_cp-v_cn)", "component_id": cid})
    elif kind == "vcvs":
        cp, cn = _terminal_pair(component, allocation.nodes, ground, "cp", "cn")
        gain = _number(params.get("gain"), field=f"{cid}.gain")
        branch = allocation.branches[cid]
        _branch_kcl(A, p, n, branch)
        _add(A, branch, p, 1.0); _add(A, branch, n, -1.0)
        _add(A, branch, cp, -gain); _add(A, branch, cn, gain)
        equations.append({"id": f"law_{cid}", "kind": "controlled_source", "text": f"v_p-v_n={gain}*(v_cp-v_cn)", "component_id": cid})
    elif kind == "ramp":
        branch = allocation.branches[cid]
        state = allocation.internal_states[cid][0]
        _branch_kcl(A, p, n, branch)
        E[state, state] = 1.0
        slope = _number(params.get("slope"), field=f"{cid}.slope")
        selected = params.get("active_modes")
        if isinstance(selected, list) and mode["id"] not in selected:
            slope = 0.0
        b[state] += slope
        _add(A, branch, p, 1.0); _add(A, branch, n, -1.0); A[branch, state] -= 1.0
        equations.append({"id": f"law_{cid}", "kind": "ramp_state", "text": f"d(x_{cid})/dt={slope}; v_p-v_n=x_{cid}", "component_id": cid})
    elif kind == "lti_block":
        branch = allocation.branches[cid]
        states = allocation.internal_states[cid]
        Am = np.asarray(params.get("A"), dtype=float)
        Bm = np.asarray(params.get("B"), dtype=float).reshape(len(states), -1)
        Cm = np.asarray(params.get("C"), dtype=float).reshape(-1, len(states))
        Dm = np.asarray(params.get("D"), dtype=float).reshape(Cm.shape[0], Bm.shape[1])
        if Bm.shape[1] != 1 or Cm.shape[0] != 1:
            raise HybridMNAError("FAIL_LTI_SISO_REQUIRED", cid)
        cp, cn = _terminal_pair(component, allocation.nodes, ground, "cp", "cn")
        _branch_kcl(A, p, n, branch)
        for local, row in enumerate(states):
            E[row, row] = 1.0
            for other, col in enumerate(states):
                A[row, col] += Am[local, other]
            _add(A, row, cp, Bm[local, 0]); _add(A, row, cn, -Bm[local, 0])
        _add(A, branch, p, 1.0); _add(A, branch, n, -1.0)
        for local, state_col in enumerate(states):
            A[branch, state_col] -= Cm[0, local]
        _add(A, branch, cp, -Dm[0, 0]); _add(A, branch, cn, Dm[0, 0])
        equations.append({"id": f"law_{cid}", "kind": "lti_state_space", "text": "xdot=A*x+B*u; y=C*x+D*u", "component_id": cid})
    else:
        raise HybridMNAError("FAIL_UNSUPPORTED_COMPONENT", f"{cid}:{kind}")
    provenance.append({"component_id": cid, "component_type": kind, "mode": mode["id"], "source": "confirmed-circuit-ir"})


def _reduce_descriptor(E: np.ndarray, A: np.ndarray, B: np.ndarray, b: np.ndarray) -> dict[str, Any]:
    U, singular, Vh = np.linalg.svd(E)
    tolerance = max(E.shape) * np.finfo(float).eps * max(1.0, float(singular[0]) if singular.size else 1.0)
    rank = int(np.count_nonzero(singular > tolerance))
    if rank == 0:
        raise HybridMNAError("FAIL_MODE_DAE_NO_DYNAMIC_STATE", "descriptor E has rank zero")
    transformed_E = U.T @ E @ Vh.T
    transformed_A = U.T @ A @ Vh.T
    transformed_B = U.T @ B
    transformed_b = U.T @ b
    E11 = transformed_E[:rank, :rank]
    A11 = transformed_A[:rank, :rank]
    A12 = transformed_A[:rank, rank:]
    A21 = transformed_A[rank:, :rank]
    A22 = transformed_A[rank:, rank:]
    B1, B2 = transformed_B[:rank], transformed_B[rank:]
    b1, b2 = transformed_b[:rank], transformed_b[rank:]
    if A22.size:
        if np.linalg.matrix_rank(A22) < A22.shape[0]:
            raise HybridMNAError("FAIL_MODE_DAE_INDEX_OR_TOPOLOGY", "algebraic block is singular")
        inv_A22_A21 = np.linalg.solve(A22, A21)
        inv_A22_B2 = np.linalg.solve(A22, B2)
        inv_A22_b2 = np.linalg.solve(A22, b2)
    else:
        inv_A22_A21 = np.zeros((0, rank))
        inv_A22_B2 = np.zeros((0, B.shape[1]))
        inv_A22_b2 = np.zeros(0)
    Ar = np.linalg.solve(E11, A11 - A12 @ inv_A22_A21)
    Br = np.linalg.solve(E11, B1 - A12 @ inv_A22_B2)
    cr = np.linalg.solve(E11, b1 - A12 @ inv_A22_b2)
    V = Vh.T
    Zx = V[:, :rank] - V[:, rank:] @ inv_A22_A21
    Zu = -V[:, rank:] @ inv_A22_B2
    z0 = -V[:, rank:] @ inv_A22_b2
    return {
        "A": Ar.tolist(), "B": Br.tolist(), "c": cr.tolist(),
        "Zx": Zx.tolist(), "Zu": Zu.tolist(), "z0": z0.tolist(),
        "basis": V[:, :rank].tolist(), "descriptor_rank": int(np.linalg.matrix_rank(E)),
        "dynamic_rank": rank, "algebraic_rank": E.shape[0] - rank,
    }


def _regularization_scales(components: list[dict[str, Any]], epsilon: float) -> tuple[float, float]:
    if not 0.0 < epsilon < 1.0:
        raise HybridMNAError("FAIL_REGULARIZATION_EPSILON", str(epsilon))
    conductances = []
    for component in components:
        if component.get("type") == "resistor":
            resistance = _number(component.get("value"), field=f"{component.get('id')}.value")
            if resistance > 0:
                conductances.append(1.0 / resistance)
    conductance_reference = max(conductances, default=1.0)
    resistance_reference = 1.0 / conductance_reference
    return epsilon * conductance_reference, epsilon * resistance_reference


def _apply_regularization(
    A: np.ndarray, mode: dict[str, Any], components: list[dict[str, Any]],
    allocation: Allocation, gmin: float, rmin: float,
) -> None:
    for node_index in allocation.nodes.values():
        A[node_index, node_index] -= gmin
    for component in components:
        kind = component.get("type")
        cid = component.get("id")
        voltage_defined = kind in {"voltage_source", "vcvs", "ramp", "lti_block"}
        if kind in {"ideal_switch", "diode"}:
            voltage_defined = (mode.get("switch_states") or {}).get(cid) == "ON"
        if voltage_defined and cid in allocation.branches:
            A[allocation.branches[cid], allocation.branches[cid]] -= rmin


def _physical_explanation(
    circuit_ir: dict[str, Any], physics_spec: dict[str, Any], energy_states: list[dict[str, Any]],
) -> dict[str, Any]:
    components = circuit_ir["components"]
    ground = circuit_ir["ground_net"]
    sources = [item for item in components if item["type"] == "voltage_source" and item.get("terminals", {}).get("n") == ground]
    source_net = sources[0]["terminals"]["p"] if sources else "source"
    inductor = next((item for item in components if item["type"] == "inductor"), None)
    switch_net = output_net = "unknown"
    if inductor:
        for candidate_switch, candidate_output in (
            (inductor["terminals"]["p"], inductor["terminals"]["n"]),
            (inductor["terminals"]["n"], inductor["terminals"]["p"]),
        ):
            if any(candidate_switch in item.get("terminals", {}).values() for item in components if item["type"] in {"ideal_switch", "diode"}):
                switch_net, output_net = candidate_switch, candidate_output
                break
    high_devices = [
        item["id"] for item in components if item["type"] in {"ideal_switch", "diode"}
        and set(item["terminals"].values()) == {source_net, switch_net}
    ]
    low_devices = [
        item["id"] for item in components if item["type"] in {"ideal_switch", "diode"}
        and set(item["terminals"].values()) == {switch_net, ground}
    ]
    capacitors = [item for item in components if item["type"] == "capacitor"]
    loads = [
        item["id"] for item in components
        if item["type"] in {"resistor", "current_source"}
        and str((item.get("parameters") or {}).get("role", "")).lower() == "load"
    ]
    esrs = [
        item["id"] for item in components if item["type"] == "resistor"
        and str((item.get("parameters") or {}).get("role", "")).lower() == "esr"
    ]
    inductor_law = None
    if inductor:
        terminals = inductor["terminals"]
        resistance = _number(
            (inductor.get("parameters") or {}).get("series_resistance", 0.0),
            field=f"{inductor['id']}.series_resistance",
        )
        inductor_law = (
            f"L*d(i_{inductor['id']})/dt="
            f"v_{terminals['p']}-v_{terminals['n']}-{resistance}*i_{inductor['id']}"
        )
    capacitor_laws = []
    for capacitor in capacitors:
        terminals = capacitor["terminals"]
        capacitor_laws.append(
            f"i_{capacitor['id']}=C*d(v_{terminals['p']}-v_{terminals['n']})/dt"
        )
    current_paths = {}
    for mode in physics_spec["modes"]:
        states = mode["switch_states"]
        conducting = sorted(cid for cid, state in states.items() if state == "ON")
        blocked = sorted(cid for cid, state in states.items() if state == "OFF")
        high_on = any(states.get(cid) == "ON" for cid in high_devices)
        low_on = any(states.get(cid) == "ON" for cid in low_devices)
        if high_on:
            path = f"{source_net} 源 → {'/'.join(high_devices)} → {switch_net} → {inductor['id'] if inductor else 'L'} → {output_net} → 负载/输出电容回路"
            story = "开关节点被高边通道拉向输入源；源同时向电感、负载和输出电容交换能量，电感电流斜率由实际 vL 决定"
            clamp = f"v_{switch_net}=v_{source_net} (理想导通约束)"
            expected_energy = "输入源注入能量；电感储能通常增加，电容按 iL-iLoad 的瞬时符号充/放电"
        elif low_on:
            path = f"{inductor['id'] if inductor else 'L'} 与 {output_net} 网络 → 负载/电容 → {'/'.join(low_devices)} 续流通道 → {switch_net}"
            story = "高边源隔离，开关节点被低边通道钳位；电感储能续流给负载/输出网络，电容承担 iL 与负载电流的差额"
            clamp = f"v_{switch_net}=v_{ground} (理想导通约束)"
            expected_energy = "输入源不经功率级注入；电感储能通常减少并向负载/电容转移"
        else:
            path = "no complete Buck commutation path is conducting"
            story = "mode semantics require review"
            clamp = "开关节点未由完整换流通道约束"
            expected_energy = "无法从已确认模式确定，应阻塞复核"
        current_paths[mode["id"]] = {
            "conducting_devices": conducting, "blocked_devices": blocked,
            "path": path, "switch_node_constraint": clamp,
            "inductor_constitutive_law": inductor_law,
            "capacitor_constitutive_laws": capacitor_laws,
            "load_elements": loads, "ESR_elements": esrs,
            "energy_story": story, "expected_energy_direction": expected_energy,
        }
    return {
        "method": "component-stamped Hybrid MNA/DAE",
        "current_paths": current_paths,
        "energy_storage": copy.deepcopy(energy_states),
        "dissipation_elements": [item["id"] for item in components if item["type"] == "resistor"]
        + [item["id"] + ".DCR" for item in components if item["type"] == "inductor" and _number((item.get("parameters") or {}).get("series_resistance", 0.0), field=f"{item['id']}.series_resistance") > 0],
        "source_exchange_elements": [item["id"] for item in components if item["type"] in {"voltage_source", "current_source", "vccs", "vcvs", "ramp", "lti_block"}],
        "no_handwritten_active_equations": True,
    }


def build_mode_dae(
    circuit_ir: dict[str, Any], physics_spec: dict[str, Any],
    *, regularization_epsilon: float | None = None,
) -> dict[str, Any]:
    validate_physics_spec(physics_spec, circuit_ir)
    components = _realize_lti_blocks(circuit_ir["components"])
    kinds = {component["type"] for component in components}
    required = {"inductor", "capacitor", "voltage_source"}
    if not required.issubset(kinds) or not ({"ideal_switch", "diode"} & kinds):
        raise HybridMNAError("FAIL_NOT_SINGLE_PHASE_BUCK_STRUCTURE", "source, switch/diode, L and C are required")
    allocation = _allocate(circuit_ir, components)
    input_names = sorted(physics_spec["inputs"])
    ground = circuit_ir["ground_net"]
    modes = []
    all_energy_states: dict[str, dict[str, Any]] = {}
    size = len(allocation.variables)
    gmin = rmin = None
    if regularization_epsilon is not None:
        gmin, rmin = _regularization_scales(components, float(regularization_epsilon))
    for mode in physics_spec["modes"]:
        if regularization_epsilon is None:
            _check_voltage_constraint_loops(components, mode)
        E = np.zeros((size, size), dtype=float)
        A = np.zeros((size, size), dtype=float)
        B = np.zeros((size, len(input_names)), dtype=float)
        b = np.zeros(size, dtype=float)
        equations: list[dict[str, Any]] = []
        provenance: list[dict[str, Any]] = []
        energy_states: list[dict[str, Any]] = []
        for component in components:
            _stamp_component(component, mode, allocation, input_names, ground, E, A, B, b, equations, provenance, energy_states)
        if gmin is not None and rmin is not None:
            _apply_regularization(A, mode, components, allocation, gmin, rmin)
            equations.append({
                "id": f"diagnostic_regularization_{mode['id']}", "kind": "regularization",
                "text": f"gmin={gmin}; rmin={rmin}; diagnostic only",
            })
        for net in circuit_ir["nets"]:
            if net["id"] != ground:
                equations.append({"id": f"kcl_{net['id']}", "kind": "KCL", "text": f"sum of stamped currents at {net['id']} equals zero", "net_id": net["id"]})
        reduced = _reduce_descriptor(E, A, B, b)
        for item in energy_states:
            all_energy_states[item["component_id"]] = item
        modes.append({
            "id": mode["id"], "E": E.tolist(), "A": A.tolist(), "B": B.tolist(), "b": b.tolist(),
            "reduced": reduced, "equations": equations, "component_provenance": provenance,
            "rank": {"descriptor": reduced["descriptor_rank"], "dynamic": reduced["dynamic_rank"], "algebraic": reduced["algebraic_rank"]},
        })
    first_E = np.asarray(modes[0]["E"])
    if any(not np.allclose(np.asarray(mode["E"]), first_E) for mode in modes[1:]):
        raise HybridMNAError("FAIL_MODE_DESCRIPTOR_STATE_MISMATCH", "all modes must share the same energy-state descriptor")
    artifact = {
        "mode_dae_version": "0.5", "case_id": circuit_ir["case_id"],
        "circuit_ir_sha256": circuit_ir["workflow"]["artifact_sha256"],
        "physics_spec_sha256": physics_spec["workflow"]["artifact_sha256"],
        "variables": allocation.variables, "inputs": input_names, "ports": copy.deepcopy(circuit_ir.get("ports", [])),
        "modes": modes, "energy_states": list(all_energy_states.values()),
        "component_inventory": copy.deepcopy(components), "ground_net": ground,
        "physical_explanation": _physical_explanation(circuit_ir, physics_spec, list(all_energy_states.values())),
        "regularization": (
            {"kind": "gmin-rmin-normalized-sweep-candidate", "epsilon": float(regularization_epsilon),
             "gmin_siemens": gmin, "rmin_ohm": rmin, "validation_status": "REGULARIZED_DIAGNOSTIC_UNVERIFIED"}
            if regularization_epsilon is not None else None
        ),
    }
    artifact = attach_physics_workflow(artifact, state="MODE_DAE", predecessor=physics_spec)
    validate_artifact(artifact, "mode_dae.schema.json")
    return artifact
