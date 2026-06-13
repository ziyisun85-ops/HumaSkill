from dataclasses import dataclass
import os
import pickle
from pathlib import Path
from typing import Optional

import numpy as np

from middle_architecture.robot_state import KinematicFrame


@dataclass
class GMTMotion:
    name: str
    path: str
    fps: float
    root_pos: np.ndarray
    root_rot: np.ndarray
    dof_pos: np.ndarray
    local_body_pos: Optional[np.ndarray]
    num_frames: int

    @property
    def root_quat(self) -> np.ndarray:
        return self.root_rot


def _resolve_motion_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.exists():
        return candidate

    gmt_root = os.environ.get("GMT_ROOT")
    for root in [Path(gmt_root)] if gmt_root else []:
        candidate = root / path
        if candidate.exists():
            return candidate

    raise FileNotFoundError(f"GMT motion file not found: {path}")


def _normalize_quat_batch(quat: np.ndarray, source: Path) -> np.ndarray:
    norms = np.linalg.norm(quat, axis=1, keepdims=True)
    if np.any(norms < 1e-8):
        raise ValueError(f"Motion {source} contains zero-length root quaternion")
    if not np.allclose(norms, 1.0, atol=1e-5):
        quat = quat / norms
    return quat.astype(np.float32)


def load_qpos_npy_motion(path: str, name: str = "") -> GMTMotion:
    resolved = _resolve_motion_path(path)
    qpos = np.load(resolved)
    if qpos.ndim != 2 or qpos.shape[1] != 30:
        raise ValueError(f"qpos npy motion must have shape (N, 30), got {qpos.shape}")
    if not np.isfinite(qpos).all():
        raise ValueError(f"Motion {resolved} contains NaN or Inf")

    qpos = np.asarray(qpos, dtype=np.float32)
    root_pos = qpos[:, 0:3]
    root_quat_wxyz = _normalize_quat_batch(qpos[:, 3:7], resolved)
    root_rot = root_quat_wxyz[:, [1, 2, 3, 0]]
    dof_pos = qpos[:, 7:30]

    motion_name = name or resolved.name
    return GMTMotion(
        name=motion_name,
        path=str(resolved),
        fps=60.0,
        root_pos=root_pos,
        root_rot=root_rot,
        dof_pos=dof_pos,
        local_body_pos=None,
        num_frames=int(root_pos.shape[0]),
    )


def load_gmt_motion(path: str, name: str = "") -> GMTMotion:
    resolved = _resolve_motion_path(path)
    suffix = resolved.suffix.lower()
    if suffix == ".npy":
        return load_qpos_npy_motion(str(resolved), name=name)
    if suffix != ".pkl":
        raise ValueError(f"Unsupported GMT motion file suffix for {resolved}: {resolved.suffix}")

    with open(resolved, "rb") as f:
        data = pickle.load(f)

    required = ["fps", "root_pos", "root_rot", "dof_pos"]
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"Motion {resolved} missing required fields: {missing}")

    root_pos = np.asarray(data["root_pos"], dtype=np.float32)
    root_rot = np.asarray(data["root_rot"], dtype=np.float32)
    dof_pos = np.asarray(data["dof_pos"], dtype=np.float32)
    local_body_pos = data.get("local_body_pos")
    if local_body_pos is not None:
        local_body_pos = np.asarray(local_body_pos, dtype=np.float32)

    if root_pos.ndim != 2 or root_pos.shape[1] != 3:
        raise ValueError(f"root_pos must have shape (N, 3), got {root_pos.shape}")
    if root_rot.ndim != 2 or root_rot.shape[1] != 4:
        raise ValueError(f"root_rot must have shape (N, 4), got {root_rot.shape}")
    if dof_pos.ndim != 2:
        raise ValueError(f"dof_pos must have shape (N, J), got {dof_pos.shape}")
    if root_pos.shape[0] != root_rot.shape[0] or root_pos.shape[0] != dof_pos.shape[0]:
        raise ValueError("root_pos, root_rot, and dof_pos frame counts must match")

    motion_name = name or resolved.name
    return GMTMotion(
        name=motion_name,
        path=str(resolved),
        fps=float(data["fps"]),
        root_pos=root_pos,
        root_rot=root_rot,
        dof_pos=dof_pos,
        local_body_pos=local_body_pos,
        num_frames=int(root_pos.shape[0]),
    )


def get_kinematic_frame(motion: GMTMotion, frame_index: int) -> KinematicFrame:
    if frame_index < 0:
        frame_index = motion.num_frames + frame_index
    if frame_index < 0 or frame_index >= motion.num_frames:
        raise IndexError(
            f"frame_index {frame_index} out of range for motion with {motion.num_frames} frames"
        )

    local_body_pos = None
    if motion.local_body_pos is not None:
        local_body_pos = motion.local_body_pos[frame_index].copy()

    return KinematicFrame(
        root_pos=motion.root_pos[frame_index].copy(),
        root_quat=motion.root_rot[frame_index].copy(),
        dof_pos=motion.dof_pos[frame_index].copy(),
        local_body_pos=local_body_pos,
    )


class GmtMotionAdapter:
    def __init__(self, motions_root: str = "."):
        self.motions_root = Path(motions_root)

    def load(self, motion_file: str) -> GMTMotion:
        path = Path(motion_file)
        if not path.exists() and not path.is_absolute():
            path = self.motions_root / motion_file
        return load_gmt_motion(str(path))

    def get_kinematic_frame(self, motion: GMTMotion, frame_index: int) -> KinematicFrame:
        return get_kinematic_frame(motion, frame_index)


MotionAdapter = GmtMotionAdapter
