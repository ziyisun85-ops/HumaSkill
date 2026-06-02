"""Tests for converting G1 retargeted motions to full qpos clips."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_METADATA_PATH = PROJECT_ROOT / "motions" / "metadata.json"
QPOS_METADATA_PATH = PROJECT_ROOT / "motions" / "metadata_qpos.json"
EXPECTED_DOF_JOINT_ORDER = [
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


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a project-local command and capture text output."""
    return subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )


def test_convert_g1_pkl_to_qpos_generates_30d_clips() -> None:
    """The qpos converter writes metadata and 30-D .npy clips."""
    assert SOURCE_METADATA_PATH.exists()
    run_command([sys.executable, "scripts/convert_g1_pkl_to_qpos.py", "--root-z-offset", "0.05"])

    assert QPOS_METADATA_PATH.exists()
    metadata = json.loads(QPOS_METADATA_PATH.read_text(encoding="utf-8"))
    assert metadata["qpos_dim"] == 30
    assert metadata["root_quaternion_source_order"] == "xyzw"
    assert metadata["root_quaternion_output_order"] == "wxyz"
    assert metadata["root_z_offset"] == 0.05
    assert metadata["dof_joint_order"] == EXPECTED_DOF_JOINT_ORDER
    motions = metadata.get("motions", [])
    assert motions

    for item in motions:
        clip_path = PROJECT_ROOT / item["output_file"]
        assert clip_path.exists(), item["output_file"]
        clip = np.load(clip_path)
        assert clip.ndim == 2
        assert clip.shape[0] > 0
        assert clip.shape[-1] == 30
        assert item["root_quaternion_source_order"] == "xyzw"
        assert item["root_quaternion_output_order"] == "wxyz"
        assert item["dof_joint_order"] == EXPECTED_DOF_JOINT_ORDER
        quat_norms = np.linalg.norm(clip[:, 3:7], axis=1)
        assert np.allclose(quat_norms, 1.0, atol=1e-4)


def test_qpos_quaternion_is_reordered_from_source_xyzw_to_mujoco_wxyz() -> None:
    """Converted qpos uses MuJoCo wxyz order, not raw PKL xyzw order."""
    run_command([sys.executable, "scripts/convert_g1_pkl_to_qpos.py", "--root-z-offset", "0.05"])

    metadata = json.loads(QPOS_METADATA_PATH.read_text(encoding="utf-8"))
    source_metadata = json.loads(SOURCE_METADATA_PATH.read_text(encoding="utf-8"))
    source_by_skill = {item["skill"]: item for item in source_metadata["motions"]}

    from scripts.convert_g1_pkl_to_qpos import (  # noqa: PLC0415
        first_motion_record,
        load_pickle,
        resolve_project_path,
    )

    for item in metadata["motions"]:
        source_item = source_by_skill[item["skill"]]
        source_path = resolve_project_path(source_item["source_file"])
        _, record = first_motion_record(load_pickle(source_path), source_path)
        raw_root_rot = np.asarray(record["root_rot"], dtype=np.float32)
        clip = np.load(PROJECT_ROOT / item["output_file"])
        np.testing.assert_allclose(clip[:, 3:7], raw_root_rot[:, [3, 0, 1, 2]], atol=1e-6)
