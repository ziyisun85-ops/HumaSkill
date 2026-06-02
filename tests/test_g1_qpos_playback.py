"""Smoke tests for MuJoCo qpos playback of converted G1 clips."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "configs" / "robot_g1_textop_mujoco.yaml"
MODEL_PATH = PROJECT_ROOT / "model" / "g1_description" / "g1_23dof.xml"
QPOS_METADATA_PATH = PROJECT_ROOT / "motions" / "metadata_qpos.json"


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a project-local command and capture text output."""
    return subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )


def test_qpos_playback_inputs_exist() -> None:
    """The playback config, matching XML, and generated metadata are present."""
    if not QPOS_METADATA_PATH.exists():
        run_command([sys.executable, "scripts/convert_g1_pkl_to_qpos.py"])

    assert CONFIG_PATH.exists()
    assert MODEL_PATH.exists()
    assert QPOS_METADATA_PATH.exists()


def test_g1_qpos_playback_reports_compatible_with_qpos() -> None:
    """The qpos playback script reports compatibility and successful playback."""
    pytest.importorskip("mujoco")
    if not QPOS_METADATA_PATH.exists():
        run_command([sys.executable, "scripts/convert_g1_pkl_to_qpos.py"])

    result = run_command([sys.executable, "scripts/test_g1_qpos_motion_in_mujoco.py"])
    output = result.stdout
    assert "Compatibility: compatible_with_qpos" in output
    assert "Playback result: qpos_playback_success" in output


def test_g1_23dof_xml_qpos_layout_matches_qpos_clips() -> None:
    """The TextOp G1 XML has freejoint + 23 scalar joints for 30-D qpos clips."""
    mujoco = pytest.importorskip("mujoco")
    if not QPOS_METADATA_PATH.exists():
        run_command([sys.executable, "scripts/convert_g1_pkl_to_qpos.py"])

    model = mujoco.MjModel.from_xml_path(str(MODEL_PATH))
    assert model.nq == 30
    assert model.nu == 23
    assert int(model.jnt_type[0]) == int(mujoco.mjtJoint.mjJNT_FREE)
    assert int(model.jnt_qposadr[0]) == 0
    assert [int(model.jnt_qposadr[index]) for index in range(1, model.njnt)] == list(range(7, 30))
