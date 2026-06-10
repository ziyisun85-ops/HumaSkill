#!/usr/bin/env python3
"""
Convert g1-moves G1 29DoF qpos clips to HumaSkill G1 23DoF qpos clips.

Input:
    qpos36 = root 7 + 29 joints

Output:
    qpos30 = root 7 + 23 joints

The default mapping removes the 6 wrist joints:
    left_wrist_roll_joint
    left_wrist_pitch_joint
    left_wrist_yaw_joint
    right_wrist_roll_joint
    right_wrist_pitch_joint
    right_wrist_yaw_joint
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np


JOINT_NAMES_29 = [
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
    "waist_roll_joint",
    "waist_pitch_joint",
    "left_shoulder_pitch_joint",
    "left_shoulder_roll_joint",
    "left_shoulder_yaw_joint",
    "left_elbow_joint",
    "left_wrist_roll_joint",
    "left_wrist_pitch_joint",
    "left_wrist_yaw_joint",
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
    "right_wrist_roll_joint",
    "right_wrist_pitch_joint",
    "right_wrist_yaw_joint",
]

# Keep legs, waist, shoulders, elbows. Drop both wrists.
KEEP_23 = list(range(13)) + [15, 16, 17, 18, 19, 22, 23, 24, 25, 26]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert g1-moves qpos36 clips to HumaSkill qpos30 clips."
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input qpos36 npy path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output qpos30 npy path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.input.is_file():
        print(f"[ERROR] input file not found: {args.input}")
        return 1

    qpos36 = np.load(args.input)

    if qpos36.ndim != 2:
        print(f"[ERROR] expected 2D array, got shape {qpos36.shape}")
        return 1

    if qpos36.shape[1] != 36:
        print(f"[ERROR] expected input shape [T, 36], got {qpos36.shape}")
        return 1

    root = qpos36[:, :7]
    joints29 = qpos36[:, 7:]

    if joints29.shape[1] != 29:
        print(f"[ERROR] expected 29 joint columns, got {joints29.shape[1]}")
        return 1

    joints23 = joints29[:, KEEP_23]
    qpos30 = np.concatenate([root, joints23], axis=1)

    if qpos30.shape[1] != 30:
        print(f"[ERROR] expected output shape [T, 30], got {qpos30.shape}")
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.save(args.output, qpos30)

    kept_names = [JOINT_NAMES_29[i] for i in KEEP_23]

    print("=" * 80)
    print("CONVERT G1-MOVES QPOS36 TO HUMASKILL QPOS30")
    print("=" * 80)
    print("input:", args.input)
    print("input shape:", qpos36.shape)
    print("output:", args.output)
    print("output shape:", qpos30.shape)
    print("nan:", np.isnan(qpos30).any())

    quat_norm = np.linalg.norm(qpos30[:, 3:7], axis=1)
    print("root xyz min:", qpos30[:, :3].min(axis=0))
    print("root xyz max:", qpos30[:, :3].max(axis=0))
    print("quat norm min/max:", quat_norm.min(), quat_norm.max())
    print("joint min/max:", qpos30[:, 7:].min(), qpos30[:, 7:].max())
    print("max frame diff:", np.abs(np.diff(qpos30, axis=0)).max())

    print("\nkept 23 joints:")
    for out_idx, name in enumerate(kept_names):
        src_idx = KEEP_23[out_idx]
        print(f"  output_joint[{out_idx:02d}] <- input_joint[{src_idx:02d}] {name}")

    print("\nfirst qpos:", qpos30[0])
    print("last qpos:", qpos30[-1])
    print("=" * 80)
    print("DONE")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
