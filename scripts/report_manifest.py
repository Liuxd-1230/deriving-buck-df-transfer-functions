#!/usr/bin/env python3
"""Create report manifests that index human-readable reports and source artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ARTIFACT_PURPOSES = {
    "intake": "检查用户输入是否完整，以及是否触发 ASK_USER_ONLY。",
    "classification": "检查 model path、model_id、validation_level。",
    "proof_object": "检查 event、sampling、sensing_layer、pulse structure。",
    "formula_origin": "检查所有公式是否来自 registry 或被显式标记为未验证来源。",
    "derivation": "检查代数消元和目标表达式。",
    "checker_result": "检查 proof、formula、normalization、power-stage dynamics、forbidden claims。",
    "bode_summary": "检查数值频响、有效频率和边界标记。",
    "mismatch_report": "检查参考数据、注入语义、区域误差。",
}


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_report_manifest(
    *, case_id: str, report_path: Path, artifact_paths: dict[str, Path | None]
) -> dict[str, Any]:
    artifacts: dict[str, Any] = {}
    for key, path in artifact_paths.items():
        if path is None:
            continue
        artifacts[key] = {
            "path": path.name,
            "purpose": ARTIFACT_PURPOSES.get(key, "证据 artifact。"),
            "sha256": _sha256(path),
        }
    return {
        "report_version": "0.4",
        "case_id": case_id,
        "report": report_path.name,
        "report_sha256": _sha256(report_path),
        "artifacts": artifacts,
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
