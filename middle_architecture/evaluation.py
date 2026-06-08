from dataclasses import dataclass
from typing import List, Optional

import numpy as np


@dataclass
class SegmentMetrics:
    maje: float
    root_height_error: float
    root_pos_error: float
    root_rot_error: float
    velocity_error: float
    accel_error: float
    success_margin: float
    phase_lag_frame: int
    num_steps: int


class EvaluationBuffer:
    def __init__(self) -> None:
        self._tracked_root_pos: List[np.ndarray] = []
        self._tracked_root_quat_xyzw: List[np.ndarray] = []
        self._tracked_dof_pos: List[np.ndarray] = []
        self._tracked_lin_vel: List[np.ndarray] = []
        self._ref_root_pos: List[np.ndarray] = []
        self._ref_root_rot_xyzw: List[np.ndarray] = []
        self._ref_dof_pos: List[np.ndarray] = []
        self._ref_lin_vel: List[np.ndarray] = []

    def record(
        self,
        step: int,
        tracked_root_pos: np.ndarray,
        tracked_root_quat_wxyz: np.ndarray,
        tracked_dof_pos: np.ndarray,
        tracked_lin_vel: np.ndarray,
        ref_root_pos: np.ndarray,
        ref_root_rot_xyzw: np.ndarray,
        ref_dof_pos: np.ndarray,
        ref_lin_vel: np.ndarray,
    ) -> None:
        q = np.asarray(tracked_root_quat_wxyz, dtype=np.float32)
        tracked_xyzw = np.array([q[1], q[2], q[3], q[0]], dtype=np.float32)
        self._tracked_root_pos.append(np.asarray(tracked_root_pos, dtype=np.float32).copy())
        self._tracked_root_quat_xyzw.append(tracked_xyzw)
        self._tracked_dof_pos.append(np.asarray(tracked_dof_pos, dtype=np.float32).copy())
        self._tracked_lin_vel.append(np.asarray(tracked_lin_vel, dtype=np.float32).copy())
        self._ref_root_pos.append(np.asarray(ref_root_pos, dtype=np.float32).copy())
        self._ref_root_rot_xyzw.append(np.asarray(ref_root_rot_xyzw, dtype=np.float32).copy())
        self._ref_dof_pos.append(np.asarray(ref_dof_pos, dtype=np.float32).copy())
        self._ref_lin_vel.append(np.asarray(ref_lin_vel, dtype=np.float32).copy())

    def num_steps(self) -> int:
        return len(self._tracked_root_pos)

    def as_arrays(self):
        return (
            np.stack(self._tracked_root_pos, axis=0),
            np.stack(self._tracked_root_quat_xyzw, axis=0),
            np.stack(self._tracked_dof_pos, axis=0),
            np.stack(self._tracked_lin_vel, axis=0),
            np.stack(self._ref_root_pos, axis=0),
            np.stack(self._ref_root_rot_xyzw, axis=0),
            np.stack(self._ref_dof_pos, axis=0),
            np.stack(self._ref_lin_vel, axis=0),
        )


def compute_segment_metrics(
    buffer: EvaluationBuffer,
    control_dt: float,
    fall_min_height: float,
    reference_fps: float = 30.0,
) -> SegmentMetrics:
    T = buffer.num_steps()
    if T == 0:
        return SegmentMetrics(
            maje=0.0, root_height_error=0.0, root_pos_error=0.0,
            root_rot_error=0.0, velocity_error=0.0, accel_error=0.0,
            success_margin=0.0, phase_lag_frame=0, num_steps=0,
        )

    (
        tracked_pos, tracked_quat, tracked_dof, tracked_vel,
        ref_pos, ref_quat, ref_dof, ref_vel,
    ) = buffer.as_arrays()

    # MAJE
    maje = float(np.mean(np.abs(tracked_dof - ref_dof)))

    # Root height error
    root_height_error = float(np.mean(np.abs(tracked_pos[:, 2] - ref_pos[:, 2])))

    # Root 2D XY position error
    xy_err = tracked_pos[:, :2] - ref_pos[:, :2]
    root_pos_error = float(np.mean(np.sqrt(np.sum(xy_err ** 2, axis=1))))

    # Root rotation error (geodesic distance)
    dot = np.clip(np.abs(np.sum(tracked_quat * ref_quat, axis=1)), 0.0, 1.0)
    root_rot_error = float(np.mean(2.0 * np.arccos(dot)))

    # Velocity error
    vel_err = tracked_vel - ref_vel
    velocity_error = float(np.mean(np.sqrt(np.sum(vel_err ** 2, axis=1))))

    # Acceleration error (central difference on positions, using control_dt)
    if T >= 3:
        tracked_accel = (tracked_pos[2:] - 2.0 * tracked_pos[1:-1] + tracked_pos[:-2]) / (control_dt ** 2)
        ref_accel = (ref_pos[2:] - 2.0 * ref_pos[1:-1] + ref_pos[:-2]) / (control_dt ** 2)
        accel_diff = tracked_accel - ref_accel
        accel_error = float(np.mean(np.sqrt(np.sum(accel_diff ** 2, axis=1))))
    else:
        accel_error = 0.0

    # Success margin
    success_margin = float(np.min(tracked_pos[:, 2])) - fall_min_height

    # Phase lag frame
    expected_frame = int(round((T - 1) * control_dt * reference_fps))
    ref_dof_all = buffer._ref_dof_pos
    n_ref = len(ref_dof_all)
    search_lo = max(0, expected_frame - 15)
    search_hi = min(n_ref - 1, expected_frame + 15)
    final_dof = tracked_dof[-1]
    best_k = expected_frame
    best_err = float("inf")
    for k in range(search_lo, search_hi + 1):
        err = float(np.sum(np.abs(final_dof - ref_dof_all[k])))
        if err < best_err:
            best_err = err
            best_k = k
    phase_lag_frame = best_k - expected_frame

    return SegmentMetrics(
        maje=maje,
        root_height_error=root_height_error,
        root_pos_error=root_pos_error,
        root_rot_error=root_rot_error,
        velocity_error=velocity_error,
        accel_error=accel_error,
        success_margin=success_margin,
        phase_lag_frame=phase_lag_frame,
        num_steps=T,
    )
