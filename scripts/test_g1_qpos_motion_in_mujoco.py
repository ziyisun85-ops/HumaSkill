"""Minimal MuJoCo qpos playback smoke test for TextOp G1 23-DoF clips."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "configs" / "robot_g1_textop_mujoco.yaml"
QPOS_METADATA_PATH = PROJECT_ROOT / "motions" / "metadata_qpos.json"
DEFAULT_SKILL = "arm_wave"


def rel(path: Path) -> str:
    """Return a stable project-relative path string."""
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_project_path(value: str) -> Path:
    """Resolve a config or metadata path relative to the project root."""
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def load_config() -> dict[str, Any]:
    """Load the TextOp G1 MuJoCo playback config."""
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def choose_motion_clip() -> Path:
    """Choose arm_wave qpos clip from metadata, falling back to the first entry."""
    metadata = json.loads(QPOS_METADATA_PATH.read_text(encoding="utf-8"))
    motions = metadata.get("motions", [])
    if not motions:
        raise ValueError(f"No qpos motion entries found in {rel(QPOS_METADATA_PATH)}")

    selected = next((item for item in motions if item.get("skill") == DEFAULT_SKILL), motions[0])
    return resolve_project_path(selected["output_file"])


def main() -> int:
    """Run qpos playback through mj_forward without rendering or controls."""
    try:
        import mujoco
    except ImportError:
        print("MuJoCo is not installed. Install with: python -m pip install mujoco")
        return 0

    config = load_config()
    xml_path = resolve_project_path(config["model_path"])
    motion_path = choose_motion_clip()

    model = mujoco.MjModel.from_xml_path(str(xml_path))
    motion = np.load(motion_path)

    print("MuJoCo model information:")
    print(f"  XML path used: {rel(xml_path)}")
    print(f"  nq: {model.nq}")
    print(f"  nv: {model.nv}")
    print(f"  nu: {model.nu}")
    print(f"  njnt: {model.njnt}")
    print(f"  nbody: {model.nbody}")
    print("Motion clip information:")
    print(f"  path: {rel(motion_path)}")
    print(f"  shape: {motion.shape}")
    print(f"  dtype: {motion.dtype}")

    if motion.ndim != 2 or motion.shape[-1] != model.nq:
        print("Compatibility: incompatible_dimension")
        print("Playback result: not_run_dimension_mismatch")
        return 0

    print("Compatibility: compatible_with_qpos")
    data = mujoco.MjData(model)
    frames = min(30, motion.shape[0])
    for index in range(frames):
        data.qpos[:] = motion[index]
        mujoco.mj_forward(model, data)

    print(f"Playback result: qpos_playback_success")
    print(f"Playback frames: {frames}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
