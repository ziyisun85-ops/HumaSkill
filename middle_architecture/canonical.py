from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np

from middle_architecture.robot_state import ReferenceFrames, RobotState


@dataclass
class CanonicalReference:
    """Tracker-neutral kinematic reference.

    Conventions for CHOREO phase 1:
    - `root_pos` is world-frame meters.
    - `root_rot` is quaternion `xyzw`, matching GMT motion pkl files.
    - `dof_pos` is the GMT G1 23-DOF order used by existing assets.
    - `fps` is source-reference frames per second.
    """

    fps: float
    root_pos: np.ndarray
    root_rot: np.ndarray
    dof_pos: np.ndarray
    local_body_pos: Optional[np.ndarray] = None
    root_quat_order: str = "xyzw"
    dof_order: str = "gmt_g1_23"
    units: str = "meters_radians"
    feature_channels: Optional[Dict[str, np.ndarray]] = None

    @staticmethod
    def from_reference_frames(reference_frames: ReferenceFrames) -> "CanonicalReference":
        return CanonicalReference(
            fps=float(reference_frames.fps),
            root_pos=np.asarray(reference_frames.root_pos, dtype=np.float32),
            root_rot=np.asarray(reference_frames.root_rot, dtype=np.float32),
            dof_pos=np.asarray(reference_frames.dof_pos, dtype=np.float32),
            local_body_pos=(
                np.asarray(reference_frames.local_body_pos, dtype=np.float32)
                if reference_frames.local_body_pos is not None
                else None
            ),
        )

    def to_reference_frames(self) -> ReferenceFrames:
        if self.root_quat_order != "xyzw":
            raise ValueError(
                "CanonicalReference.to_reference_frames requires root_quat_order='xyzw'"
            )
        return ReferenceFrames(
            fps=float(self.fps),
            root_pos=np.asarray(self.root_pos, dtype=np.float32),
            root_rot=np.asarray(self.root_rot, dtype=np.float32),
            dof_pos=np.asarray(self.dof_pos, dtype=np.float32),
            local_body_pos=(
                np.asarray(self.local_body_pos, dtype=np.float32)
                if self.local_body_pos is not None
                else None
            ),
        )


@dataclass
class CanonicalRobotState:
    """Tracker-neutral robot state.

    `root_quat` is `wxyz`, matching MuJoCo qpos[3:7] and the existing
    `RobotState` convention.
    """

    root_pos: np.ndarray
    root_quat: np.ndarray
    dof_pos: np.ndarray
    root_lin_vel: np.ndarray
    root_ang_vel: np.ndarray
    dof_vel: np.ndarray
    root_quat_order: str = "wxyz"
    dof_order: str = "gmt_g1_23"
    units: str = "meters_radians"

    @staticmethod
    def from_robot_state(state: RobotState) -> "CanonicalRobotState":
        return CanonicalRobotState(
            root_pos=np.asarray(state.root_pos, dtype=np.float32),
            root_quat=np.asarray(state.root_quat, dtype=np.float32),
            dof_pos=np.asarray(state.dof_pos, dtype=np.float32),
            root_lin_vel=np.asarray(state.root_lin_vel, dtype=np.float32),
            root_ang_vel=np.asarray(state.root_ang_vel, dtype=np.float32),
            dof_vel=np.asarray(state.dof_vel, dtype=np.float32),
        )

    def to_robot_state(self) -> RobotState:
        if self.root_quat_order != "wxyz":
            raise ValueError("CanonicalRobotState.to_robot_state requires root_quat_order='wxyz'")
        return RobotState(
            root_pos=np.asarray(self.root_pos, dtype=np.float32),
            root_quat=np.asarray(self.root_quat, dtype=np.float32),
            dof_pos=np.asarray(self.dof_pos, dtype=np.float32),
            root_lin_vel=np.asarray(self.root_lin_vel, dtype=np.float32),
            root_ang_vel=np.asarray(self.root_ang_vel, dtype=np.float32),
            dof_vel=np.asarray(self.dof_vel, dtype=np.float32),
        )


@dataclass
class CanonicalAction:
    """Tracker-neutral action container for future tracker support."""

    action_type: str
    values: np.ndarray
    joint_order: str = "gmt_g1_23"
    scale: float = 1.0
