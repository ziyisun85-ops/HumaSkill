"""Convert selected G1 retargeted pickle motions to full 30-D qpos clips."""

from __future__ import annotations

import argparse
import json
import pickle
import warnings
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MOTION_DIR = PROJECT_ROOT / "motions"
SOURCE_METADATA_PATH = MOTION_DIR / "metadata.json"
QPOS_METADATA_PATH = MOTION_DIR / "metadata_qpos.json"
MODEL_PATH = PROJECT_ROOT / "model" / "g1_description" / "g1_23dof.xml"
ROOT_TRANS_FIELD = "root_trans_offset"
ROOT_ROT_FIELD = "root_rot"
DOF_FIELD = "dof"
EXPECTED_DOF_DIM = 23
EXPECTED_QPOS_DIM = 30
DEFAULT_ROOT_Z_OFFSET = 0.05
ROOT_QUAT_SOURCE_ORDER = "xyzw"
ROOT_QUAT_MUJOCO_ORDER = "wxyz"
DOF_JOINT_NAMES = [
    "left_hip_pitch_joint",
    "left_hip_roll_joint",
    "left_hip_yaw_joint",
    "left_knee_joint",
    "left_ankle_pitch_joint",
    "left_ankle_roll_joint",
    "right_hip_pitch_joint",
    "right_hip_roll_joint",
    "right_hip_yaw_joint",
    "right_knee_joint",
    "right_ankle_pitch_joint",
    "right_ankle_roll_joint",
    "waist_yaw_joint",
    "left_shoulder_pitch_joint",
    "left_shoulder_roll_joint",
    "left_shoulder_yaw_joint",
    "left_elbow_joint",
    "left_wrist_roll_joint",
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
    "right_wrist_roll_joint",
]


class PathFixUnpickler(pickle.Unpickler):
    """Load Linux-created pathlib paths on Windows."""

    def find_class(self, module: str, name: str) -> Any:
        if module == "pathlib" and name == "PosixPath":
            return PurePosixPath
        return super().find_class(module, name)


def rel(path: Path) -> str:
    """Return a stable project-relative path string."""
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_project_path(value: str) -> Path:
    """Resolve a metadata path relative to the project root."""
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def load_pickle(path: Path) -> Any:
    """Load a pickle file while tolerating PosixPath objects on Windows."""
    with path.open("rb") as file:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return PathFixUnpickler(file).load()


def first_motion_record(obj: Any, source_path: Path) -> tuple[str, dict[str, Any]]:
    """Return the first nested motion record from the observed pickle layout."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, dict):
                return str(key), value
        return "<root>", obj
    raise ValueError(f"Expected dict pickle structure in {rel(source_path)}, got {type(obj).__name__}")


def require_2d_field(record: dict[str, Any], field: str, width: int, frames: int | None = None) -> np.ndarray:
    """Extract and validate a 2D array field."""
    if field not in record:
        raise KeyError(f"Missing required field {field!r}")
    array = np.asarray(record[field], dtype=np.float32)
    if array.ndim != 2:
        raise ValueError(f"{field} must be 2D, got shape {array.shape}")
    if array.shape[1] != width:
        raise ValueError(f"{field} must have width {width}, got shape {array.shape}")
    if frames is not None and array.shape[0] != frames:
        raise ValueError(f"{field} frame count mismatch: expected {frames}, got {array.shape[0]}")
    return array


def fps_from_record(record: dict[str, Any]) -> int:
    """Read FPS from a motion record, defaulting to 30."""
    fps_value = record.get("fps", 30)
    if hasattr(fps_value, "shape"):
        return int(np.asarray(fps_value).item())
    return int(fps_value)


def root_quat_xyzw_to_mujoco_wxyz(root_rot: np.ndarray) -> np.ndarray:
    """Convert PKL root quaternions from xyzw to MuJoCo freejoint wxyz order.

    MuJoCo freejoint qpos layout is [x, y, z, qw, qx, qy, qz].
    The retargeted PKL files store root_rot as [qx, qy, qz, qw].
    Treating the PKL values as wxyz rotates the robot sideways in the viewer.
    """
    quat = root_rot[:, [3, 0, 1, 2]].astype(np.float32, copy=False)
    norms = np.linalg.norm(quat, axis=1)
    if not np.allclose(norms, 1.0, atol=1e-4):
        raise ValueError(
            f"Root quaternion norms must be close to 1 after xyzw->wxyz conversion; "
            f"range=({norms.min()}, {norms.max()})"
        )
    return quat


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Convert selected G1 PKL motions to qpos clips.")
    parser.add_argument(
        "--root-z-offset",
        type=float,
        default=DEFAULT_ROOT_Z_OFFSET,
        help="Offset in meters added to qpos[:, 2] after qpos construction.",
    )
    return parser.parse_args()


def convert_motion(item: dict[str, Any], root_z_offset: float) -> dict[str, Any]:
    """Convert one metadata motion entry into a qpos clip."""
    source_file = item["source_file"]
    source_path = resolve_project_path(source_file)
    obj = load_pickle(source_path)
    source_record, record = first_motion_record(obj, source_path)

    root_trans = require_2d_field(record, ROOT_TRANS_FIELD, 3)
    root_rot = require_2d_field(record, ROOT_ROT_FIELD, 4, frames=root_trans.shape[0])
    dof = require_2d_field(record, DOF_FIELD, EXPECTED_DOF_DIM, frames=root_trans.shape[0])

    root_quat_wxyz = root_quat_xyzw_to_mujoco_wxyz(root_rot)
    qpos = np.concatenate([root_trans, root_quat_wxyz, dof], axis=1).astype(np.float32, copy=False)
    qpos[:, 2] += np.float32(root_z_offset)
    if qpos.shape != (root_trans.shape[0], EXPECTED_QPOS_DIM):
        raise ValueError(f"qpos must have shape [T, {EXPECTED_QPOS_DIM}], got {qpos.shape}")

    skill = item["skill"]
    output_path = MOTION_DIR / f"{skill}_qpos.npy"
    np.save(output_path, qpos)

    return {
        "skill": skill,
        "source_file": source_file,
        "source_record": source_record,
        "output_file": rel(output_path),
        "fields": [ROOT_TRANS_FIELD, ROOT_ROT_FIELD, DOF_FIELD],
        "qpos_layout": ["root_x", "root_y", "root_z", "root_qw", "root_qx", "root_qy", "root_qz"]
        + DOF_JOINT_NAMES,
        "root_quaternion_source_order": ROOT_QUAT_SOURCE_ORDER,
        "root_quaternion_output_order": ROOT_QUAT_MUJOCO_ORDER,
        "root_z_offset": root_z_offset,
        "dof_joint_order": DOF_JOINT_NAMES,
        "shape": list(qpos.shape),
        "dtype": str(qpos.dtype),
        "fps": fps_from_record(record),
        "notes": (
            "Converted from root translation, root rotation, and 23-DoF joint trajectory. "
            "PKL root_rot is stored as xyzw and is reordered to MuJoCo freejoint wxyz."
        ),
    }


def main() -> int:
    """Convert all motions listed in motions/metadata.json to qpos clips."""
    args = parse_args()
    if not SOURCE_METADATA_PATH.exists():
        raise FileNotFoundError(f"Missing source metadata: {rel(SOURCE_METADATA_PATH)}")
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Missing matching MuJoCo model: {rel(MODEL_PATH)}")

    MOTION_DIR.mkdir(parents=True, exist_ok=True)
    source_metadata = json.loads(SOURCE_METADATA_PATH.read_text(encoding="utf-8"))
    source_motions = source_metadata.get("motions", [])
    if not source_motions:
        raise ValueError(f"No motion entries found in {rel(SOURCE_METADATA_PATH)}")

    converted = [convert_motion(item, args.root_z_offset) for item in source_motions]
    metadata = {
        "robot_name": "unitree_g1_textop_23dof",
        "model_path": rel(MODEL_PATH),
        "source_metadata": rel(SOURCE_METADATA_PATH),
        "motion_dir": rel(MOTION_DIR),
        "motion_format": "qpos",
        "qpos_dim": EXPECTED_QPOS_DIM,
        "fields": [ROOT_TRANS_FIELD, ROOT_ROT_FIELD, DOF_FIELD],
        "qpos_layout": ["root_x", "root_y", "root_z", "root_qw", "root_qx", "root_qy", "root_qz"]
        + DOF_JOINT_NAMES,
        "root_quaternion_source_order": ROOT_QUAT_SOURCE_ORDER,
        "root_quaternion_output_order": ROOT_QUAT_MUJOCO_ORDER,
        "root_z_offset": args.root_z_offset,
        "dof_joint_order": DOF_JOINT_NAMES,
        "motions": converted,
    }
    QPOS_METADATA_PATH.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print(f"Number of converted qpos motions: {len(converted)}")
    for item in converted:
        print(f"- skill: {item['skill']}")
        print(f"  source_file: {item['source_file']}")
        print(f"  fields: {item['fields']}")
        print(f"  output_file: {item['output_file']}")
        print(f"  shape: {item['shape']}")
        print(f"  dtype: {item['dtype']}")
    print(f"Metadata: {rel(QPOS_METADATA_PATH)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
