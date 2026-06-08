from dataclasses import dataclass
from typing import Optional

import numpy as np

from middle_architecture.robot_state import DEFAULT_SCORE_WEIGHTS, MatchConfig


@dataclass
class MatchResult:
    motion_path: str
    start_frame: int
    end_frame: Optional[int]
    score: float
    reason: str


def _local_derive_frame_vel(motion, frame_idx: int) -> np.ndarray:
    fps = float(motion.fps)
    n = motion.num_frames
    if frame_idx <= 0:
        return fps * (motion.root_pos[1] - motion.root_pos[0])
    if frame_idx >= n - 1:
        return fps * (motion.root_pos[-1] - motion.root_pos[-2])
    return fps * (motion.root_pos[frame_idx + 1] - motion.root_pos[frame_idx - 1]) / 2.0


class MotionMatcher:
    def __init__(self, match_config: Optional[MatchConfig] = None) -> None:
        self.match_config = match_config or MatchConfig()

    def select(self, robot_state, skill_spec, motion, duration=None) -> MatchResult:
        if self.match_config.mode == "pose_search":
            return self._pose_search_select(robot_state, skill_spec, motion, duration)
        return self._static_select(robot_state, skill_spec, motion, duration)

    def _static_select(self, robot_state, skill_spec, motion, duration=None) -> MatchResult:
        start_frame = int(skill_spec.default_start_frame)
        if duration is not None:
            num_frames = int(round(float(duration) * float(motion.fps)))
            end_frame = min(start_frame + num_frames, motion.num_frames)
        else:
            end_frame = skill_spec.default_end_frame
        if end_frame is None:
            end_frame = motion.num_frames
        return MatchResult(
            motion_path=skill_spec.motion_file,
            start_frame=start_frame,
            end_frame=int(end_frame),
            score=0.0,
            reason="static_skill_spec_match",
        )

    def _pose_search_select(self, robot_state, skill_spec, motion, duration=None) -> MatchResult:
        default_start = int(skill_spec.default_start_frame)
        window = self.match_config.search_window
        search_end = min(motion.num_frames - 1, default_start + window)
        weights = self.match_config.score_weights or DEFAULT_SCORE_WEIGHTS

        best_frame = default_start
        best_score = float("inf")
        for frame_idx in range(default_start, search_end + 1):
            s = self._pose_score(robot_state, motion, frame_idx, weights)
            if s < best_score:
                best_score = s
                best_frame = frame_idx

        frame_shift = best_frame - default_start
        if duration is not None:
            num_frames = int(round(float(duration) * float(motion.fps)))
            end_frame = min(best_frame + num_frames, motion.num_frames)
        elif skill_spec.default_end_frame is not None:
            end_frame = min(skill_spec.default_end_frame + frame_shift, motion.num_frames)
        else:
            end_frame = motion.num_frames

        return MatchResult(
            motion_path=skill_spec.motion_file,
            start_frame=best_frame,
            end_frame=int(end_frame),
            score=float(best_score),
            reason="pose_search_match",
        )

    def _pose_score(self, robot_state, motion, frame_idx: int, weights: dict) -> float:
        w_dof = float(weights.get("dof_pos", 1.0))
        w_quat = float(weights.get("root_quat", 0.5))
        w_vel = float(weights.get("velocity", 0.3))
        w_height = float(weights.get("root_height", 0.2))

        # DOF position error
        dof_err = float(np.mean(np.abs(motion.dof_pos[frame_idx] - robot_state.dof_pos)))

        # Root quaternion geodesic distance
        ref_xyzw = np.asarray(motion.root_rot[frame_idx], dtype=np.float32)
        q_wxyz = np.asarray(robot_state.root_quat, dtype=np.float32)
        tracked_xyzw = np.array([q_wxyz[1], q_wxyz[2], q_wxyz[3], q_wxyz[0]], dtype=np.float32)
        ref_norm = np.linalg.norm(ref_xyzw)
        trk_norm = np.linalg.norm(tracked_xyzw)
        if ref_norm > 1e-8:
            ref_xyzw = ref_xyzw / ref_norm
        if trk_norm > 1e-8:
            tracked_xyzw = tracked_xyzw / trk_norm
        dot = float(np.clip(np.abs(np.dot(ref_xyzw, tracked_xyzw)), 0.0, 1.0))
        quat_err = 2.0 * float(np.arccos(dot))

        # Root linear velocity error
        ref_vel = _local_derive_frame_vel(motion, frame_idx)
        vel_err = float(np.linalg.norm(ref_vel - robot_state.root_lin_vel))

        # Root height error
        height_err = abs(float(motion.root_pos[frame_idx, 2]) - float(robot_state.root_pos[2]))

        return w_dof * dof_err + w_quat * quat_err + w_vel * vel_err + w_height * height_err
