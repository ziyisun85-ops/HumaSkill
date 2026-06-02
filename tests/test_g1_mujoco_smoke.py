"""Smoke tests for the minimal G1 MuJoCo dimension-check script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "configs" / "robot_g1_mujoco.yaml"
METADATA_PATH = PROJECT_ROOT / "motions" / "metadata.json"


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a project-local command and capture text output."""
    return subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )


def test_g1_mujoco_config_model_and_metadata_exist() -> None:
    """The smoke-test config points at an existing model and generated metadata."""
    if not METADATA_PATH.exists():
        run_command([sys.executable, "scripts/convert_g1_pkl_to_npy.py"])

    assert CONFIG_PATH.exists()
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    assert (PROJECT_ROOT / config["model_path"]).exists()
    assert METADATA_PATH.exists()

    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    assert metadata.get("motions")


def test_g1_mujoco_smoke_script_prints_model_and_motion_info() -> None:
    """The MuJoCo smoke script runs far enough to print model and motion info."""
    pytest.importorskip("mujoco")
    if not METADATA_PATH.exists():
        run_command([sys.executable, "scripts/convert_g1_pkl_to_npy.py"])

    result = run_command([sys.executable, "scripts/test_g1_motion_in_mujoco.py"])
    output = result.stdout
    assert "MuJoCo model information:" in output
    assert "Motion clip information:" in output
    assert "Motion compatibility:" in output
