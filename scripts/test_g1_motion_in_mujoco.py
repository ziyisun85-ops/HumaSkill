"""Minimal Unitree G1 MuJoCo load and motion-dimension smoke test."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "configs" / "robot_g1_mujoco.yaml"


def rel(path: Path) -> str:
    """Return a stable project-relative path string."""
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_project_path(value: str) -> Path:
    """Resolve a config path relative to the project root."""
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def load_config() -> dict[str, Any]:
    """Load the G1 MuJoCo config."""
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def choose_xml_path(config: dict[str, Any], mujoco: Any) -> tuple[Path, Any]:
    """Load the first configured XML file that MuJoCo accepts."""
    preferred = list(config.get("preferred_xml", []))
    model_path = config.get("model_path")
    if model_path and model_path not in preferred:
        preferred.insert(0, model_path)

    errors: list[str] = []
    for candidate in preferred:
        xml_path = resolve_project_path(str(candidate))
        if not xml_path.exists():
            errors.append(f"{rel(xml_path)}: missing")
            continue
        try:
            return xml_path, mujoco.MjModel.from_xml_path(str(xml_path))
        except Exception as exc:  # noqa: BLE001 - try all configured XMLs.
            errors.append(f"{rel(xml_path)}: {type(exc).__name__}: {exc}")

    raise RuntimeError("No configured MuJoCo XML could be loaded:\n" + "\n".join(errors))


def choose_motion_clip(config: dict[str, Any]) -> Path:
    """Choose the first converted clip listed in metadata, or any .npy clip."""
    motion_dir = resolve_project_path(str(config.get("motion_dir", "motions")))
    metadata_path = motion_dir / "metadata.json"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        for item in metadata.get("motions", []):
            output_file = item.get("output_file")
            if output_file:
                candidate = resolve_project_path(output_file)
                if candidate.exists():
                    return candidate

    clips = sorted(motion_dir.glob("*.npy")) if motion_dir.exists() else []
    if clips:
        return clips[0]
    raise FileNotFoundError(f"No .npy motion clips found under {rel(motion_dir)}")


def compatibility_label(motion_dim: int, model: Any) -> str:
    """Classify the motion dimension against MuJoCo qpos/action dimensions."""
    if motion_dim == int(model.nq):
        return "compatible_with_qpos"
    if motion_dim == int(model.nu):
        return "compatible_with_action"
    return "incompatible_dimension"


def main() -> int:
    """Run the minimal load/dimension check without opening a viewer."""
    try:
        import mujoco
    except ImportError:
        print("MuJoCo is not installed. Install with: python -m pip install mujoco")
        return 0

    config = load_config()
    xml_path, model = choose_xml_path(config, mujoco)
    motion_path = choose_motion_clip(config)
    motion = np.load(motion_path)
    motion_dim = int(motion.shape[-1]) if motion.ndim > 0 else 0
    compatibility = compatibility_label(motion_dim, model)

    print("MuJoCo model information:")
    print(f"  XML path used: {rel(xml_path)}")
    print(f"  nq: {model.nq}")
    print(f"  nv: {model.nv}")
    print(f"  nu: {model.nu}")
    print(f"  number of joints: {model.njnt}")
    print(f"  number of actuators: {model.nu}")
    print("Motion clip information:")
    print(f"  path: {rel(motion_path)}")
    print(f"  shape: {motion.shape}")
    print(f"  dtype: {motion.dtype}")
    print(f"Motion compatibility: {compatibility}")

    smoke_result = "not_run_dimension_mismatch"
    if compatibility in {"compatible_with_qpos", "compatible_with_action"}:
        data = mujoco.MjData(model)
        steps = min(30, len(motion)) if motion.ndim >= 2 else 0
        for index in range(steps):
            if compatibility == "compatible_with_qpos":
                data.qpos[:] = motion[index]
            else:
                data.ctrl[:] = motion[index]
            mujoco.mj_step(model, data)
        smoke_result = f"stepped_{steps}_frames"
    print(f"Simulation smoke result: {smoke_result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
