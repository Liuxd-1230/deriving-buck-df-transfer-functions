#!/usr/bin/env python3
"""Validation and deterministic checkout rendering for v0.5 Circuit IR."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import html
import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from physics_workflow import attach_physics_workflow, content_hash, verify_physics_workflow
from schema_validation import validate_artifact


DIMENSIONS = {
    "ohm": {"kg": 1, "m": 2, "s": -3, "A": -2, "K": 0, "mol": 0, "cd": 0},
    "F": {"kg": -1, "m": -2, "s": 4, "A": 2, "K": 0, "mol": 0, "cd": 0},
    "H": {"kg": 1, "m": 2, "s": -2, "A": -2, "K": 0, "mol": 0, "cd": 0},
    "V": {"kg": 1, "m": 2, "s": -3, "A": -1, "K": 0, "mol": 0, "cd": 0},
    "A": {"kg": 0, "m": 0, "s": 0, "A": 1, "K": 0, "mol": 0, "cd": 0},
    "s": {"kg": 0, "m": 0, "s": 1, "A": 0, "K": 0, "mol": 0, "cd": 0},
    "1": {"kg": 0, "m": 0, "s": 0, "A": 0, "K": 0, "mol": 0, "cd": 0},
}
REQUIRED_UNIT = {
    "resistor": "ohm", "capacitor": "F", "inductor": "H",
    "voltage_source": "V", "current_source": "A",
}


class CircuitIRError(ValueError):
    """Raised when a Circuit IR cannot be trusted as topology evidence."""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _image_dimensions(path: Path) -> tuple[int, int]:
    if path.suffix.lower() == ".svg":
        root = ElementTree.fromstring(path.read_text(encoding="utf-8"))
        width = str(root.get("width", "")).removesuffix("px")
        height = str(root.get("height", "")).removesuffix("px")
        if width and height:
            return int(round(float(width))), int(round(float(height)))
        view_box = root.get("viewBox", "").replace(",", " ").split()
        if len(view_box) == 4:
            return int(round(float(view_box[2]))), int(round(float(view_box[3])))
        raise CircuitIRError("FAIL_SVG_DIMENSIONS")
    import matplotlib.pyplot as plt

    image = plt.imread(path)
    height, width = image.shape[:2]
    return int(width), int(height)


def circuit_content_hash(ir: dict[str, Any]) -> str:
    return content_hash(ir, "confirmation")


def _terminal_nets(component: dict[str, Any]) -> set[str]:
    return {str(net) for net in (component.get("terminals") or {}).values()}


def validate_buck_topology(ir: dict[str, Any]) -> list[str]:
    """Recognise the minimum single-phase Buck power path without using names."""
    components = ir.get("components", [])
    ground = str(ir.get("ground_net"))
    voltage_sources = [item for item in components if item.get("type") == "voltage_source"]
    inductors = [item for item in components if item.get("type") == "inductor"]
    capacitors = [item for item in components if item.get("type") == "capacitor"]
    commutators = [item for item in components if item.get("type") in {"ideal_switch", "diode"}]
    resistors = [item for item in components if item.get("type") == "resistor"]
    errors: list[str] = []
    if not voltage_sources or not inductors or not capacitors or len(commutators) < 2:
        return ["FAIL_NOT_SINGLE_PHASE_BUCK_STRUCTURE"]

    source_positive = {
        str(item["terminals"].get("p")) for item in voltage_sources
        if str(item["terminals"].get("n")) == ground
    }
    candidates: list[tuple[str, str]] = []
    commutator_edges = [_terminal_nets(item) for item in commutators]
    for inductor in inductors:
        terminals = inductor.get("terminals") or {}
        if "p" not in terminals or "n" not in terminals:
            continue
        for switch_net, output_net in ((str(terminals["p"]), str(terminals["n"])), (str(terminals["n"]), str(terminals["p"]))):
            high_path = any({switch_net, source} == edge for source in source_positive for edge in commutator_edges)
            low_path = any({switch_net, ground} == edge for edge in commutator_edges)
            if high_path and low_path:
                candidates.append((switch_net, output_net))
    if len(set(candidates)) != 1:
        errors.append("FAIL_BUCK_COMMUTATION_PATH_AMBIGUOUS")
        return errors

    _, output_net = candidates[0]
    load_present = any(
        _terminal_nets(item) == {output_net, ground}
        for item in components if item.get("type") in {"resistor", "current_source"}
    )
    if not load_present:
        errors.append("ASK_USER_ONLY:LOAD_NOT_IDENTIFIED")
    capacitor_path = any(_terminal_nets(item) == {output_net, ground} for item in capacitors)
    if not capacitor_path:
        for resistor in resistors:
            edge = _terminal_nets(resistor)
            if output_net not in edge or len(edge) != 2:
                continue
            intermediate = next(iter(edge - {output_net}))
            if any(_terminal_nets(item) == {intermediate, ground} for item in capacitors):
                capacitor_path = True
                break
    if not capacitor_path:
        errors.append("FAIL_OUTPUT_CAPACITOR_PATH_NOT_IDENTIFIED")
    return errors


def validate_circuit_ir(ir: dict[str, Any], *, require_confirmation: bool = False) -> list[str]:
    validate_artifact(ir, "circuit_ir.schema.json")
    errors: list[str] = []
    net_ids = [str(item.get("id")) for item in ir.get("nets", [])]
    if len(net_ids) != len(set(net_ids)):
        errors.append("FAIL_DUPLICATE_NET_ID")
    component_ids = [str(item.get("id")) for item in ir.get("components", [])]
    if len(component_ids) != len(set(component_ids)):
        errors.append("FAIL_DUPLICATE_COMPONENT_ID")
    if ir.get("ground_net") not in set(net_ids):
        errors.append("FAIL_GROUND_NET_NOT_DECLARED")
    for component in ir.get("components", []):
        for terminal, net in (component.get("terminals") or {}).items():
            if net not in set(net_ids):
                errors.append(f"FAIL_UNKNOWN_NET:{component.get('id')}:{terminal}:{net}")
        expected = REQUIRED_UNIT.get(str(component.get("type")))
        quantity = component.get("value")
        if expected and not isinstance(quantity, dict):
            errors.append(f"FAIL_COMPONENT_VALUE_REQUIRED:{component.get('id')}")
        elif expected and quantity.get("si_dimension") != DIMENSIONS[expected]:
            errors.append(f"FAIL_COMPONENT_DIMENSION:{component.get('id')}:{expected}")
        if component.get("type") not in {"comparator", "timer"}:
            orientation = component.get("orientation") or {}
            terminals = component.get("terminals") or {}
            required_orientation = {"voltage_positive", "voltage_negative", "current_from", "current_to"}
            if set(orientation) < required_orientation:
                errors.append(f"ASK_USER_ONLY:ORIENTATION_NOT_CONFIRMED:{component.get('id')}")
            elif any(orientation[name] not in terminals for name in required_orientation):
                errors.append(f"FAIL_ORIENTATION_TERMINAL:{component.get('id')}")
        elif component.get("type") == "comparator":
            terminals = component.get("terminals") or {}
            if not {"positive", "negative"}.issubset(terminals):
                errors.append(f"ASK_USER_ONLY:COMPARATOR_POLARITY:{component.get('id')}")
            parameters = component.get("parameters") or {}
            positive = parameters.get("positive_expression")
            negative = parameters.get("negative_expression")
            guard = parameters.get("guard_expression")
            if not all(isinstance(item, str) and item.strip() for item in (positive, negative, guard)):
                errors.append(f"ASK_USER_ONLY:COMPARATOR_EXPRESSIONS:{component.get('id')}")
            else:
                import sympy as sp
                try:
                    if sp.simplify(sp.sympify(guard) - (sp.sympify(negative) - sp.sympify(positive))) != 0:
                        errors.append(f"FAIL_COMPARATOR_GUARD_POLARITY:{component.get('id')}")
                except (sp.SympifyError, TypeError):
                    errors.append(f"FAIL_COMPARATOR_EXPRESSION:{component.get('id')}")

    terminal_counts = {net: 0 for net in net_ids}
    adjacency = {net: set() for net in net_ids}
    for component in ir.get("components", []):
        nets = sorted(_terminal_nets(component))
        for net in nets:
            if net in terminal_counts:
                terminal_counts[net] += 1
        for left in nets:
            for right in nets:
                if left != right and left in adjacency and right in adjacency:
                    adjacency[left].add(right)
    dangling = [net for net, count in terminal_counts.items() if net != ir.get("ground_net") and count < 2]
    if dangling:
        errors.append("FAIL_DANGLING_NET:" + ",".join(sorted(dangling)))
    if ir.get("ground_net") in adjacency:
        reached = {str(ir["ground_net"])}
        frontier = list(reached)
        while frontier:
            current = frontier.pop()
            for neighbour in adjacency[current] - reached:
                reached.add(neighbour)
                frontier.append(neighbour)
        floating = sorted(set(net_ids) - reached)
        if floating:
            errors.append("FAIL_FLOATING_SUBCIRCUIT:" + ",".join(floating))
    errors.extend(validate_buck_topology(ir))
    open_blocking = [
        item.get("id") for item in ir.get("ambiguities", [])
        if item.get("blocking") and item.get("status") != "RESOLVED"
    ]
    if open_blocking:
        errors.append("ASK_USER_ONLY:OPEN_BLOCKING_AMBIGUITIES:" + ",".join(map(str, open_blocking)))
    if require_confirmation or ir.get("status") == "TOPOLOGY_CONFIRMED":
        if ir.get("status") != "TOPOLOGY_CONFIRMED":
            errors.append("ASK_USER_ONLY:TOPOLOGY_NOT_CONFIRMED")
        confirmation = ir.get("confirmation") or {}
        if confirmation.get("confirmed_content_sha256") != circuit_content_hash(ir):
            errors.append("FAIL_CONFIRMATION_HASH_MISMATCH")
        try:
            verify_physics_workflow(ir, expected_state="TOPOLOGY_CONFIRMED")
        except ValueError as exc:
            errors.append(f"FAIL_V05_WORKFLOW:{exc}")
    return errors


def build_image_intake(image_path: Path, case_id: str) -> dict[str, Any]:
    width, height = _image_dimensions(image_path)
    artifact = {
        "intake_version": "0.5",
        "case_id": case_id,
        "source_image": {
            "filename": image_path.name,
            "sha256": file_sha256(image_path),
            "width_px": int(width),
            "height_px": int(height),
        },
        "rule": "image evidence only; no topology is authoritative at this state",
    }
    artifact = attach_physics_workflow(artifact, state="IMAGE_INTAKE")
    validate_artifact(artifact, "image_intake.schema.json")
    return artifact


def attach_proposed_ir(ir: dict[str, Any], image_intake: dict[str, Any]) -> dict[str, Any]:
    verify_physics_workflow(image_intake, expected_state="IMAGE_INTAKE")
    proposed = copy.deepcopy(ir)
    proposed["status"] = "PROPOSED"
    proposed.pop("confirmation", None)
    proposed.pop("workflow", None)
    if proposed.get("case_id") != image_intake.get("case_id"):
        raise CircuitIRError("FAIL_CASE_ID_MISMATCH")
    if proposed.get("source_image") != image_intake.get("source_image"):
        raise CircuitIRError("FAIL_SOURCE_IMAGE_PROVENANCE_MISMATCH")
    proposed = attach_physics_workflow(proposed, state="CIRCUIT_IR_PROPOSED", predecessor=image_intake)
    validate_artifact(proposed, "circuit_ir.schema.json")
    return proposed


def confirm_circuit_ir(proposed: dict[str, Any], *, notes: list[str] | None = None) -> dict[str, Any]:
    verify_physics_workflow(proposed, expected_state="CIRCUIT_IR_PROPOSED")
    confirmed = copy.deepcopy(proposed)
    confirmed.pop("workflow", None)
    confirmed["status"] = "TOPOLOGY_CONFIRMED"
    confirmed["confirmation"] = {
        "confirmed_by": "user",
        "notes": list(notes or []),
        "confirmed_content_sha256": "0" * 64,
    }
    confirmed["confirmation"]["confirmed_content_sha256"] = circuit_content_hash(confirmed)
    confirmed = attach_physics_workflow(confirmed, state="TOPOLOGY_CONFIRMED", predecessor=proposed)
    errors = validate_circuit_ir(confirmed, require_confirmation=True)
    if errors:
        raise CircuitIRError("; ".join(errors))
    return confirmed


def verify_source_image(ir: dict[str, Any], image_path: Path) -> None:
    if file_sha256(image_path) != ir["source_image"]["sha256"]:
        raise CircuitIRError("FAIL_SOURCE_IMAGE_HASH_MISMATCH")


def render_checkout(ir: dict[str, Any], image_path: Path, output_path: Path) -> None:
    if image_path.suffix.lower() == ".svg":
        verify_source_image(ir, image_path)
        width, height = _image_dimensions(image_path)
        if width != ir["source_image"]["width_px"] or height != ir["source_image"]["height_px"]:
            raise CircuitIRError("FAIL_SOURCE_IMAGE_DIMENSION_MISMATCH")
        if output_path.suffix.lower() != ".svg":
            raise CircuitIRError("SVG checkout output must use the .svg suffix")
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        overlays = []
        for component_index, component in enumerate(ir.get("components", []), start=1):
            x0, y0, x1, y1 = component["bbox"]
            x, y = x0 * width, y0 * height
            w, h = (x1 - x0) * width, (y1 - y0) * height
            component_id = html.escape(str(component["id"]), quote=True)
            overlays.append(
                f'<g data-component-id="{component_id}">'
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="#00a6d6" stroke-width="2"/>'
                f'<text x="{x}" y="{max(10, y - 3)}" font-size="10" font-weight="bold" fill="#006b85">C{component_index:02d}:{component_id}</text>'
                '</g>'
            )
        for net_index, net in enumerate(ir.get("nets", []), start=1):
            regions = net.get("evidence_regions") or []
            if regions:
                x0, y0, x1, y1 = regions[0]
                x, y = ((x0 + x1) / 2.0) * width, ((y0 + y1) / 2.0) * height
            else:
                x, y = width - 115.0, 18.0 + net_index * 15.0
            net_id = html.escape(str(net["id"]), quote=True)
            overlays.append(
                f'<g data-node-id="{net_id}">'
                f'<circle cx="{x}" cy="{y}" r="4" fill="#2ca02c" stroke="white" stroke-width="1"/>'
                f'<text x="{x + 6}" y="{y + 4}" font-size="10" font-weight="bold" fill="#18751c">N{net_index:02d}:{net_id}</text>'
                '</g>'
            )
        content = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f'<image href="data:image/svg+xml;base64,{encoded}" width="{width}" height="{height}"/>'
            + "".join(overlays) + "</svg>"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        return
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    verify_source_image(ir, image_path)
    image = plt.imread(image_path)
    height, width = image.shape[:2]
    if width != ir["source_image"]["width_px"] or height != ir["source_image"]["height_px"]:
        raise CircuitIRError("FAIL_SOURCE_IMAGE_DIMENSION_MISMATCH")
    fig, axis = plt.subplots(figsize=(max(8, width / 120), max(5, height / 120)), dpi=120)
    axis.imshow(image)
    colors = {"comparator": "#d62728", "ideal_switch": "#ff7f0e", "diode": "#ff7f0e"}
    for component_index, component in enumerate(ir.get("components", []), start=1):
        x0, y0, x1, y1 = component["bbox"]
        color = colors.get(component["type"], "#00a6d6")
        axis.add_patch(Rectangle((x0 * width, y0 * height), (x1 - x0) * width, (y1 - y0) * height, fill=False, lw=2, ec=color))
        axis.text(x0 * width, max(0, y0 * height - 3), f"C{component_index:02d}:{component['id']}", color=color, fontsize=9, weight="bold", bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none"})
    for net_index, net in enumerate(ir.get("nets", []), start=1):
        regions = net.get("evidence_regions") or []
        if regions:
            x0, y0, x1, y1 = regions[0]
            x, y = ((x0 + x1) / 2.0) * width, ((y0 + y1) / 2.0) * height
        else:
            x, y = width - 115.0, 18.0 + net_index * 15.0
        axis.scatter([x], [y], s=20, c="#2ca02c", edgecolors="white", linewidths=0.7)
        axis.text(x + 6, y + 4, f"N{net_index:02d}:{net['id']}", color="#18751c", fontsize=8, weight="bold", bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "#2ca02c"})
    axis.set_axis_off()
    axis.set_title(f"Circuit IR checkout — {ir['case_id']} — {ir['status']}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build, validate, confirm, or render v0.5 Circuit IR artifacts.")
    subparsers = parser.add_subparsers(dest="command")
    intake = subparsers.add_parser("image-intake")
    intake.add_argument("--image", required=True); intake.add_argument("--case-id", required=True); intake.add_argument("--out", required=True)
    propose = subparsers.add_parser("propose")
    propose.add_argument("--ir", required=True); propose.add_argument("--image-intake", required=True); propose.add_argument("--out", required=True)
    confirm = subparsers.add_parser("confirm")
    confirm.add_argument("--ir", required=True); confirm.add_argument("--out", required=True); confirm.add_argument("--note", action="append", default=[])
    validate = subparsers.add_parser("validate")
    validate.add_argument("--ir", required=True); validate.add_argument("--image"); validate.add_argument("--overlay"); validate.add_argument("--require-confirmation", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "image-intake":
            result = build_image_intake(Path(args.image), args.case_id)
            Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        elif args.command == "propose":
            raw = json.loads(Path(args.ir).read_text(encoding="utf-8"))
            image_intake = json.loads(Path(args.image_intake).read_text(encoding="utf-8"))
            result = attach_proposed_ir(raw, image_intake)
            Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        elif args.command == "confirm":
            proposed = json.loads(Path(args.ir).read_text(encoding="utf-8"))
            result = confirm_circuit_ir(proposed, notes=args.note)
            Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        elif args.command == "validate":
            ir = json.loads(Path(args.ir).read_text(encoding="utf-8"))
            errors = validate_circuit_ir(ir, require_confirmation=args.require_confirmation)
            if errors:
                raise CircuitIRError("; ".join(errors))
            if args.image or args.overlay:
                if not (args.image and args.overlay):
                    raise CircuitIRError("--image and --overlay must be used together")
                render_checkout(ir, Path(args.image), Path(args.overlay))
        else:
            parser.error("a command is required")
        print("PASS")
        return 0
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
