"""MuJoCo qpos playback backend for generated motion clips."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np

from humaskill.backends.base_backend import BaseBackend, ExecutionResult


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = "model/g1_description/g1_23dof.xml"
DEFAULT_MOTION_DIR = "motions"
DEFAULT_SKILL_CLIPS = {
    "stand_ready": "stand_ready_qpos.npy",
    "arm_wave": "arm_wave_qpos.npy",
    "final_pose": "final_pose_qpos.npy",
}


class MotionClipMujocoBackend(BaseBackend):
    """Play generated qpos motion clips through MuJoCo.

    This backend intentionally implements qpos playback only. It does not
    perform actuator control, policy inference, or online motion generation.
    """

    def __init__(
        self,
        model_path: str = DEFAULT_MODEL_PATH,
        motion_dir: str = DEFAULT_MOTION_DIR,
        viewer: bool = False,
        viewer_fps: float = 30.0,
        viewer_loop: bool = False,
        skill_clips: dict[str, str] | None = None,
    ) -> None:
        """Initialize the motion clip MuJoCo backend."""
        if viewer_fps <= 0:
            raise ValueError(f"viewer_fps must be > 0, got {viewer_fps}")
        self.model_path = self._resolve_path(model_path)
        self.motion_dir = self._resolve_path(motion_dir)
        self.viewer = viewer
        self.viewer_fps = float(viewer_fps)
        self.viewer_loop = viewer_loop
        self.skill_clips = dict(skill_clips or DEFAULT_SKILL_CLIPS)

    def execute(self, skill_name: str, duration: float) -> ExecutionResult:
        """Execute one skill by playing its qpos clip."""
        if not skill_name:
            raise ValueError("skill_name must not be empty")
        if duration <= 0:
            raise ValueError(f"duration must be > 0, got {duration}")

        motion_path = self._motion_path_for_skill(skill_name)
        base_info = {
            "backend": "motion_clip_mujoco",
            "model_path": self._display_path(self.model_path),
            "motion_path": self._display_path(motion_path) if motion_path else None,
            "mode": "qpos_playback",
            "viewer": self.viewer,
            "viewer_fps": self.viewer_fps,
            "viewer_loop": self.viewer_loop,
        }

        if motion_path is None or not motion_path.exists():
            return self._failed(skill_name, duration, "missing_motion_clip", base_info)
        if not self.model_path.exists():
            return self._failed(skill_name, duration, "mujoco_load_failed", base_info)

        try:
            import mujoco
        except ImportError:
            return self._failed(skill_name, duration, "missing_mujoco", base_info)

        try:
            model = mujoco.MjModel.from_xml_path(str(self.model_path))
        except Exception as exc:  # noqa: BLE001 - convert backend failure to result.
            info = {**base_info, "error": f"{type(exc).__name__}: {exc}"}
            return self._failed(skill_name, duration, "mujoco_load_failed", info)

        try:
            motion = np.load(motion_path)
        except Exception as exc:  # noqa: BLE001 - bad local clip should not crash harness.
            info = {**base_info, "error": f"{type(exc).__name__}: {exc}"}
            return self._failed(skill_name, duration, "playback_failed", info)

        info = {
            **base_info,
            "motion_shape": list(motion.shape),
            "model_nq": int(model.nq),
            "model_nv": int(model.nv),
            "model_nu": int(model.nu),
        }
        if motion.ndim != 2 or motion.shape[1] != model.nq:
            return self._failed(skill_name, duration, "dimension_mismatch", info)

        data = mujoco.MjData(model)
        try:
            steps = self._play_with_viewer(mujoco, model, data, motion) if self.viewer else self._play_headless(
                mujoco,
                model,
                data,
                motion,
            )
        except KeyboardInterrupt:
            steps = int(min(len(motion), max(0, getattr(self, "_last_frame_count", 0))))
        except Exception as exc:  # noqa: BLE001 - convert backend failure to result.
            reason = "viewer_failed" if self.viewer else "playback_failed"
            return self._failed(
                skill_name,
                duration,
                reason,
                {**info, "error": f"{type(exc).__name__}: {exc}"},
            )

        final_obs = {
            "qpos_head": data.qpos[: min(7, model.nq)].tolist(),
            "sim_time": float(data.time),
        }
        return ExecutionResult(
            status="success",
            skill=skill_name,
            duration=duration,
            steps=steps,
            reward=None,
            final_obs=final_obs,
            info=info,
            failure_reason=None,
        )

    def _play_headless(self, mujoco: Any, model: Any, data: Any, motion: np.ndarray) -> int:
        """Run through the qpos clip once without opening a viewer."""
        for frame_index, frame in enumerate(motion, start=1):
            self._last_frame_count = frame_index
            data.qpos[:] = frame
            mujoco.mj_forward(model, data)
        return int(len(motion))

    def _play_with_viewer(self, mujoco: Any, model: Any, data: Any, motion: np.ndarray) -> int:
        """Run qpos playback in a passive MuJoCo viewer."""
        import mujoco.viewer

        frame_period = 1.0 / self.viewer_fps
        steps = 0
        with mujoco.viewer.launch_passive(model, data) as viewer:
            while viewer.is_running():
                for frame in motion:
                    if not viewer.is_running():
                        break
                    start = time.perf_counter()
                    data.qpos[:] = frame
                    mujoco.mj_forward(model, data)
                    viewer.sync()
                    steps += 1
                    self._last_frame_count = steps
                    elapsed = time.perf_counter() - start
                    if elapsed < frame_period:
                        time.sleep(frame_period - elapsed)
                if not self.viewer_loop:
                    break
        return steps

    def _motion_path_for_skill(self, skill_name: str) -> Path | None:
        """Return the qpos clip path for a skill, if configured."""
        clip_name = self.skill_clips.get(skill_name)
        if clip_name is None:
            return None
        clip_path = Path(clip_name)
        if clip_path.is_absolute():
            return clip_path
        return self.motion_dir / clip_path

    def _failed(
        self,
        skill_name: str,
        duration: float,
        reason: str,
        info: dict[str, Any],
    ) -> ExecutionResult:
        """Build a failed execution result."""
        return ExecutionResult(
            status="failed",
            skill=skill_name,
            duration=duration,
            steps=0,
            reward=None,
            final_obs=None,
            info=info,
            failure_reason=reason,
        )

    def _resolve_path(self, value: str) -> Path:
        """Resolve relative paths against the project root."""
        path = Path(value)
        if path.is_absolute():
            return path
        return PROJECT_ROOT / path

    def _display_path(self, path: Path | None) -> str | None:
        """Return a stable project-relative display path."""
        if path is None:
            return None
        try:
            return path.relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            return path.as_posix()
