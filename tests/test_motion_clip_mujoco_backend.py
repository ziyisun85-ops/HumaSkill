"""Tests for the MuJoCo motion-clip qpos playback backend."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from humaskill.backends.base_backend import ExecutionResult
from humaskill.backends.motion_clip_mujoco_backend import MotionClipMujocoBackend
from humaskill.main import create_backend, main, parse_args


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "model" / "g1_description" / "g1_23dof.xml"
ARM_WAVE_QPOS = PROJECT_ROOT / "motions" / "arm_wave_qpos.npy"


def test_motion_clip_mujoco_backend_importable() -> None:
    """MotionClipMujocoBackend can be imported and instantiated."""
    backend = MotionClipMujocoBackend(viewer=False)
    assert isinstance(backend, MotionClipMujocoBackend)
    assert backend.viewer is False


def test_create_backend_accepts_motion_clip_mujoco() -> None:
    """The CLI backend factory accepts motion_clip_mujoco."""
    backend = create_backend(
        "motion_clip_mujoco",
        fail_prob=0.0,
        seed=42,
        viewer=False,
        viewer_fps=24.0,
        viewer_loop=False,
    )
    assert isinstance(backend, MotionClipMujocoBackend)
    assert backend.viewer_fps == 24.0


def test_cli_parser_accepts_viewer_args() -> None:
    """CLI parser accepts viewer-related arguments."""
    args = parse_args(
        [
            "--text",
            "跳一段舞",
            "--duration",
            "8",
            "--backend",
            "motion_clip_mujoco",
            "--viewer",
            "--viewer-fps",
            "30",
            "--viewer-loop",
        ]
    )
    assert args.backend == "motion_clip_mujoco"
    assert args.viewer is True
    assert args.viewer_fps == 30
    assert args.viewer_loop is True


def test_missing_clip_returns_failed_execution_result(tmp_path: Path) -> None:
    """Missing qpos clip returns failed ExecutionResult instead of crashing."""
    backend = MotionClipMujocoBackend(motion_dir=str(tmp_path), viewer=False)
    result = backend.execute("arm_wave", 1.0)

    assert isinstance(result, ExecutionResult)
    assert result.status == "failed"
    assert result.failure_reason == "missing_motion_clip"


def test_unknown_skill_returns_missing_motion_clip() -> None:
    """Unsupported skills fail with missing_motion_clip."""
    backend = MotionClipMujocoBackend(viewer=False)
    result = backend.execute("body_sway", 1.0)

    assert result.status == "failed"
    assert result.failure_reason == "missing_motion_clip"


def test_existing_qpos_clip_succeeds_headless_if_mujoco_installed() -> None:
    """Existing qpos clip returns success in headless mode when MuJoCo is installed."""
    pytest.importorskip("mujoco")
    assert MODEL_PATH.exists()
    assert ARM_WAVE_QPOS.exists()

    backend = MotionClipMujocoBackend(viewer=False)
    result = backend.execute("arm_wave", 1.0)

    assert result.status == "success"
    assert result.failure_reason is None
    assert result.steps > 0
    assert result.info["viewer"] is False
    assert result.info["mode"] == "qpos_playback"
    assert result.info["motion_shape"][-1] == result.info["model_nq"]


def test_main_accepts_motion_clip_mujoco_backend(tmp_path: Path) -> None:
    """main runs with motion_clip_mujoco without opening the viewer."""
    output_path = tmp_path / "demo_mujoco_log.json"
    exit_code = main(
        [
            "--text",
            "跳一段舞",
            "--duration",
            "8",
            "--backend",
            "motion_clip_mujoco",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert output_path.exists()
    log_data = json.loads(output_path.read_text(encoding="utf-8"))
    assert log_data["request"]["backend"] == "motion_clip_mujoco"
    assert log_data["request"]["viewer"] is False


def test_viewer_mode_not_opened_during_tests() -> None:
    """Tests instantiate viewer mode but do not execute it."""
    backend = MotionClipMujocoBackend(viewer=True, viewer_fps=30, viewer_loop=True)
    assert backend.viewer is True
    assert backend.viewer_fps == 30
    assert backend.viewer_loop is True
