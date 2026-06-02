"""Visual MuJoCo qpos playback for generated G1 qpos clips.

This script is intentionally standalone. It does not use or modify the
HumaSkill backend interfaces.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "configs" / "robot_g1_textop_mujoco.yaml"
QPOS_METADATA_PATH = PROJECT_ROOT / "motions" / "metadata_qpos.json"
DEFAULT_CLIP = "arm_wave_qpos.npy"


def rel(path: Path) -> str:
    """Return a stable project-relative path string."""
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_project_path(value: str) -> Path:
    """Resolve a config, metadata, or CLI path relative to the project root."""
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def load_config() -> dict[str, Any]:
    """Load the TextOp G1 MuJoCo playback config."""
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def metadata_clip_map() -> dict[str, Path]:
    """Return useful clip aliases from metadata_qpos.json when it exists."""
    if not QPOS_METADATA_PATH.exists():
        return {}

    metadata = json.loads(QPOS_METADATA_PATH.read_text(encoding="utf-8"))
    clips: dict[str, Path] = {}
    for item in metadata.get("motions", []):
        output_file = item.get("output_file")
        if not output_file:
            continue
        path = resolve_project_path(output_file)
        skill = str(item.get("skill", ""))
        if skill:
            clips[skill] = path
            clips[f"{skill}_qpos"] = path
            clips[f"{skill}_qpos.npy"] = path
        clips[path.name] = path
    return clips


def choose_clip(clip_arg: str | None, motion_dir: Path) -> Path:
    """Resolve a requested clip path/name/skill to a .npy file."""
    clips = metadata_clip_map()
    if clip_arg:
        if clip_arg in clips:
            return clips[clip_arg]
        requested = resolve_project_path(clip_arg)
        if requested.exists():
            return requested
        in_motion_dir = motion_dir / clip_arg
        if in_motion_dir.exists():
            return in_motion_dir
        raise FileNotFoundError(f"Could not find qpos clip: {clip_arg}")

    if DEFAULT_CLIP in clips:
        return clips[DEFAULT_CLIP]
    default_path = motion_dir / DEFAULT_CLIP
    if default_path.exists():
        return default_path

    candidates = sorted(motion_dir.glob("*_qpos.npy")) if motion_dir.exists() else []
    if not candidates:
        raise FileNotFoundError(f"No *_qpos.npy clips found under {rel(motion_dir)}")
    return candidates[0]


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="View generated G1 qpos clips in the MuJoCo viewer.",
    )
    parser.add_argument(
        "--clip",
        default=None,
        help=(
            "Clip path, filename, or metadata skill name. "
            "Examples: arm_wave, arm_wave_qpos.npy, motions/arm_wave_qpos.npy"
        ),
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=None,
        help="Playback FPS. Defaults to motion_fps from config.",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Loop playback until the viewer is closed.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Maximum frames to play from the selected clip.",
    )
    return parser.parse_args()


def validate_motion(motion: np.ndarray, model: Any, clip_path: Path) -> None:
    """Validate qpos motion shape against the loaded MuJoCo model."""
    if motion.ndim != 2:
        raise ValueError(f"{rel(clip_path)} must be a 2D qpos array, got shape {motion.shape}")
    if motion.shape[1] != model.nq:
        raise ValueError(
            f"{rel(clip_path)} has qpos dim {motion.shape[1]}, but model nq is {model.nq}"
        )
    if motion.shape[0] == 0:
        raise ValueError(f"{rel(clip_path)} contains no frames")


def main() -> int:
    """Open a MuJoCo viewer and play qpos frames."""
    try:
        import mujoco
        import mujoco.viewer
    except ImportError:
        print("MuJoCo is not installed. Install with: python -m pip install mujoco")
        return 0

    args = parse_args()
    config = load_config()
    xml_path = resolve_project_path(config["model_path"])
    motion_dir = resolve_project_path(str(config.get("motion_dir", "motions")))
    fps = float(args.fps if args.fps is not None else config.get("motion_fps", 30))
    if fps <= 0:
        raise ValueError(f"--fps must be positive, got {fps}")
    if args.max_frames is not None and args.max_frames <= 0:
        raise ValueError(f"--max-frames must be positive, got {args.max_frames}")

    clip_path = choose_clip(args.clip, motion_dir)
    model = mujoco.MjModel.from_xml_path(str(xml_path))
    data = mujoco.MjData(model)
    motion = np.load(clip_path)
    validate_motion(motion, model, clip_path)

    frame_count = motion.shape[0]
    if args.max_frames is not None:
        frame_count = min(frame_count, args.max_frames)
    frame_period = 1.0 / fps

    print("G1 qpos visual playback")
    print(f"  XML path: {rel(xml_path)}")
    print(f"  clip: {rel(clip_path)}")
    print(f"  motion shape: {motion.shape}")
    print(f"  model nq/nv/nu: {model.nq}/{model.nv}/{model.nu}")
    print(f"  playback fps: {fps:g}")
    print(f"  frames this pass: {frame_count}")
    print(f"  loop: {args.loop}")

    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            for frame_index in range(frame_count):
                if not viewer.is_running():
                    break
                start = time.perf_counter()
                data.qpos[:] = motion[frame_index]
                mujoco.mj_forward(model, data)
                viewer.sync()
                elapsed = time.perf_counter() - start
                if elapsed < frame_period:
                    time.sleep(frame_period - elapsed)
            if not args.loop:
                break

        # Keep the final frame visible until the user closes the viewer.
        while viewer.is_running() and not args.loop:
            viewer.sync()
            time.sleep(0.05)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
