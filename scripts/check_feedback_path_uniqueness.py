#!/usr/bin/env python3
"""Check that typed feedback-path aliases are not closed twice."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _system(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("linear_equation_system"), dict):
        return payload["linear_equation_system"]
    return payload


def _coefficient_definitions(system: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item["symbol"]): item
        for item in system.get("coefficient_definitions") or []
        if isinstance(item, dict) and item.get("symbol")
    }


def _active_block_ids(system: dict[str, Any]) -> set[str]:
    return {
        str(item.get("block_id"))
        for item in system.get("active_equations") or []
        if isinstance(item, dict) and item.get("block_id")
    }


def _block_path_tuple(block: dict[str, Any], coefficients: dict[str, dict[str, Any]]) -> tuple[str, str, str] | None:
    coefficient = coefficients.get(str(block.get("coefficient"))) if block.get("coefficient") else None
    path = block.get("feedback_path") or (coefficient or {}).get("feedback_path")
    if not path:
        return None
    source = block.get("from") or block.get("input") or (coefficient or {}).get("from")
    dest = block.get("to") or block.get("output") or (coefficient or {}).get("to")
    return (str(path), str(source), str(dest))


def check_feedback_path_uniqueness(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    denominator_paths = [
        str(item.get("feedback_path"))
        for item in payload.get("denominator_provenance") or []
        if isinstance(item, dict) and item.get("feedback_path")
    ]
    duplicate_denominator = [path for path, count in Counter(denominator_paths).items() if count > 1]
    if duplicate_denominator:
        errors.append("FAIL_DOUBLE_CLOSED_FEEDBACK_PATH")

    system = _system(payload)
    coefficients = _coefficient_definitions(system)
    active_ids = _active_block_ids(system)
    aliases: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for block in system.get("blocks") or []:
        if not isinstance(block, dict) or str(block.get("id")) not in active_ids:
            continue
        key = _block_path_tuple(block, coefficients)
        if key:
            aliases[key].append(str(block.get("coefficient") or block.get("id")))
    if any(len(set(names)) > 1 for names in aliases.values()):
        errors.append("FAIL_DUPLICATE_SENSING_PATH_ALIAS")

    status = "FAIL" if errors else ("PASS" if denominator_paths or aliases else "NOT_APPLICABLE")
    return {
        "status": status,
        "blocking": bool(errors),
        "errors": sorted(set(errors)),
        "warnings": [],
        "reason": "; ".join(sorted(set(errors))) or "feedback paths are unique",
        "artifact": "derivation.json",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check feedback path alias and denominator uniqueness.")
    parser.add_argument("--artifact", required=True)
    args = parser.parse_args()
    result = check_feedback_path_uniqueness(json.loads(Path(args.artifact).read_text(encoding="utf-8")))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"PASS", "WARN", "NOT_APPLICABLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
