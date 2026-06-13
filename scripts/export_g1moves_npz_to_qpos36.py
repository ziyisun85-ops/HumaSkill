#!/usr/bin/env python3
"""Export qpos36 directly from a g1-moves NPZ reference file.

This script does not load a policy, does not train, and does not run MuJoCo.
It simply concatenates root position, root quaternion, and the 29 G1 joints
from the reference NPZ into a HumaSkill-friendly qpos array.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np


def resolve_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{label} file not found: {path}")


def load_reference(npz_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    required_keys = ["fps", "joint_pos", "body_pos_w", "body_quat_w"]
    with np.load(npz_path) as data:
        missing = [key for key in required_keys if key not in data]
        if missing:
            raise KeyError(f"NPZ missing required key(s): {', '.join(missing)}")

        joint_pos = np.asarray(data["joint_pos"], dtype=np.float32)
        body_pos_w = np.asarray(data["body_pos_w"], dtype=np.float32)
        body_quat_w = np.asarray(data["body_quat_w"], dtype=np.float32)

    if joint_pos.ndim != 2 or joint_pos.shape[1] != 29:
        raise ValueError(f"Expected joint_pos shape [T, 29], got {joint_pos.shape}")
    if body_pos_w.ndim != 3 or body_pos_w.shape[0] != joint_pos.shape[0] or body_pos_w.shape[2] != 3:
        raise ValueError(f"Expected body_pos_w shape [T, N, 3], got {body_pos_w.shape}")
    if body_quat_w.ndim != 3 or body_quat_w.shape[:2] != body_pos_w.shape[:2] or body_quat_w.shape[2] != 4:
        raise ValueError(f"Expected body_quat_w shape [T, N, 4], got {body_quat_w.shape}")

    return joint_pos, body_pos_w, body_quat_w


def format_minmax(name: str, values: np.ndarray) -> str:
    return f"{name} min/max: {float(np.min(values)):.6g} / {float(np.max(values)):.6g}"


def export_qpos36(npz_path: Path, output_path: Path, root_body_index: int) -> np.ndarray:
    joint_pos, body_pos_w, body_quat_w = load_reference(npz_path)

    num_bodies = body_pos_w.shape[1]
    if root_body_index < 0 or root_body_index >= num_bodies:
        raise IndexError(
            f"--root-body-index must be in [0, {num_bodies - 1}], got {root_body_index}"
        )

    root_pos = body_pos_w[:, root_body_index, :]
    root_quat = body_quat_w[:, root_body_index, :]
    qpos36 = np.concatenate([root_pos, root_quat, joint_pos], axis=1).astype(np.float32)

    if qpos36.ndim != 2 or qpos36.shape[1] != 36:
        raise RuntimeError(f"Internal qpos36 shape error: expected [T, 36], got {qpos36.shape}")
    if not np.isfinite(qpos36).all():
        raise ValueError("qpos36 contains NaN or Inf")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(output_path, qpos36)
    return qpos36


def print_summary(output_path: Path, qpos36: np.ndarray, root_body_index: int) -> None:
    root_pos = qpos36[:, :3]
    root_quat = qpos36[:, 3:7]
    joints29 = qpos36[:, 7:36]
    quat_norm = np.linalg.norm(root_quat, axis=1)
    max_frame_diff = 0.0
    if qpos36.shape[0] > 1:
        max_frame_diff = float(np.max(np.abs(np.diff(qpos36, axis=0))))

    print(f"output path: {output_path}")
    print(f"root body index: {root_body_index}")
    print(f"shape: {qpos36.shape}")
    print(f"nan: {np.isnan(qpos36).any()}")
    print(f"root quat norm min/max: {float(quat_norm.min()):.6g} / {float(quat_norm.max()):.6g}")
    print(format_minmax("root xyz", root_pos))
    print(format_minmax("joint", joints29))
    print(f"max frame diff: {max_frame_diff:.6g}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export qpos36 directly from g1-moves NPZ reference data."
    )
    parser.add_argument("--npz", required=True, help="Path to g1-moves NPZ reference file.")
    parser.add_argument("--output", required=True, help="Output .npy path for qpos36.")
    parser.add_argument(
        "--root-body-index",
        type=int,
        default=0,
        help="Body index in body_pos_w/body_quat_w to use as qpos root.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        npz_path = resolve_path(args.npz)
        output_path = resolve_path(args.output)
        require_file(npz_path, "NPZ")

        qpos36 = export_qpos36(npz_path, output_path, args.root_body_index)
        print_summary(output_path, qpos36, args.root_body_index)
        return 0

    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
