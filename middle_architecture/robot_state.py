from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np

DEFAULT_SCORE_WEIGHTS: Dict[str, float] = {
    "dof_pos": 1.0,
    "root_quat": 0.5,
    "velocity": 0.3,
    "root_height": 0.2,
}


@dataclass
class ReferenceFrames:
    fps: float
    root_pos: np.ndarray
    root_rot: np.ndarray
    dof_pos: np.ndarray
    local_body_pos: Optional[np.ndarray] = None


@dataclass
class ReferenceSegment:
    segment_id: str
    segment_type: str
    skill_name: Optional[str]
    reference_frames: ReferenceFrames
    source_motion_path: Optional[str] = None
    start_frame: Optional[int] = None
    end_frame: Optional[int] = None
    target_duration: Optional[float] = None
    transition_type: Optional[str] = None
    from_skill: Optional[str] = None
    to_skill: Optional[str] = None
    reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class KinematicFrame:
    root_pos: np.ndarray
    root_quat: np.ndarray
    dof_pos: np.ndarray
    local_body_pos: Optional[np.ndarray] = None


@dataclass
class RobotState:
    root_pos: np.ndarray
    root_quat: np.ndarray
    dof_pos: np.ndarray
    root_lin_vel: np.ndarray
    root_ang_vel: np.ndarray
    dof_vel: np.ndarray


@dataclass
class MatchConfig:
    mode: str = "static"
    search_window: int = 60
    score_weights: Optional[Dict[str, float]] = None


@dataclass
class TransitionMetrics:
    seam_vel_delta: float
    seam_accel_delta: float
    peak_jerk: float
    mean_jerk: float
    auj: float
    interpolation_mode: str
    num_frames: int
