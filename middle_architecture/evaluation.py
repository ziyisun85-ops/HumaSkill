from dataclasses import dataclass
from typing import Dict, List, Optional

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
    max_abs_roll: float = 0.0
    max_abs_pitch: float = 0.0
    mean_qvel_norm: float = 0.0
    max_qvel_norm: float = 0.0
    mean_root_velocity_norm: float = 0.0
    max_root_velocity_norm: float = 0.0
    foot_contact_switch_count: int = 0
    foot_contact_consistency: float = 1.0
    foot_sliding: float = 0.0


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
        self._base_roll: List[float] = []
        self._base_pitch: List[float] = []
        self._qvel_norm: List[float] = []
        self._root_velocity_norm: List[float] = []
        self._foot_contacts: List[Dict[str, bool]] = []
        self._foot_positions: List[Dict[str, np.ndarray]] = []

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
        base_roll: Optional[float] = None,
        base_pitch: Optional[float] = None,
        qvel_norm: Optional[float] = None,
        root_velocity_norm: Optional[float] = None,
        foot_contacts: Optional[Dict[str, bool]] = None,
        foot_positions: Optional[Dict[str, np.ndarray]] = None,
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
        self._base_roll.append(float(base_roll) if base_roll is not None else 0.0)
        self._base_pitch.append(float(base_pitch) if base_pitch is not None else 0.0)
        self._qvel_norm.append(float(qvel_norm) if qvel_norm is not None else 0.0)
        self._root_velocity_norm.append(
            float(root_velocity_norm)
            if root_velocity_norm is not None
            else float(np.linalg.norm(tracked_lin_vel))
        )
        self._foot_contacts.append(dict(foot_contacts or {}))
        self._foot_positions.append(
            {k: np.asarray(v, dtype=np.float32).copy() for k, v in (foot_positions or {}).items()}
        )

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

    visual = compute_visual_smoothness_metrics(buffer)

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
        max_abs_roll=visual["max_abs_roll"],
        max_abs_pitch=visual["max_abs_pitch"],
        mean_qvel_norm=visual["mean_qvel_norm"],
        max_qvel_norm=visual["max_qvel_norm"],
        mean_root_velocity_norm=visual["mean_root_velocity_norm"],
        max_root_velocity_norm=visual["max_root_velocity_norm"],
        foot_contact_switch_count=visual["foot_contact_switch_count"],
        foot_contact_consistency=visual["foot_contact_consistency"],
        foot_sliding=visual["foot_sliding"],
    )


def compute_visual_smoothness_metrics(buffer: EvaluationBuffer) -> dict:
    T = buffer.num_steps()
    if T == 0:
        return {
            "max_abs_roll": 0.0,
            "max_abs_pitch": 0.0,
            "mean_qvel_norm": 0.0,
            "max_qvel_norm": 0.0,
            "mean_root_velocity_norm": 0.0,
            "max_root_velocity_norm": 0.0,
            "foot_contact_switch_count": 0,
            "foot_contact_consistency": 1.0,
            "foot_sliding": 0.0,
        }

    roll = np.asarray(buffer._base_roll, dtype=np.float32)
    pitch = np.asarray(buffer._base_pitch, dtype=np.float32)
    qvel_norm = np.asarray(buffer._qvel_norm, dtype=np.float32)
    root_vel_norm = np.asarray(buffer._root_velocity_norm, dtype=np.float32)

    switch_count = 0
    possible_switches = 0
    foot_names = sorted(
        set().union(*[set(item.keys()) for item in buffer._foot_contacts])
        if buffer._foot_contacts
        else set()
    )
    for i in range(1, T):
        for foot in foot_names:
            possible_switches += 1
            if bool(buffer._foot_contacts[i - 1].get(foot, False)) != bool(
                buffer._foot_contacts[i].get(foot, False)
            ):
                switch_count += 1
    foot_contact_consistency = (
        1.0 - float(switch_count) / float(possible_switches)
        if possible_switches > 0
        else 1.0
    )

    foot_sliding = 0.0
    for i in range(1, T):
        for foot in foot_names:
            if not (
                buffer._foot_contacts[i - 1].get(foot, False)
                and buffer._foot_contacts[i].get(foot, False)
            ):
                continue
            prev_pos = buffer._foot_positions[i - 1].get(foot)
            cur_pos = buffer._foot_positions[i].get(foot)
            if prev_pos is None or cur_pos is None:
                continue
            foot_sliding += float(np.linalg.norm(cur_pos[:2] - prev_pos[:2]))

    return {
        "max_abs_roll": float(np.max(np.abs(roll))) if roll.size else 0.0,
        "max_abs_pitch": float(np.max(np.abs(pitch))) if pitch.size else 0.0,
        "mean_qvel_norm": float(np.mean(qvel_norm)) if qvel_norm.size else 0.0,
        "max_qvel_norm": float(np.max(qvel_norm)) if qvel_norm.size else 0.0,
        "mean_root_velocity_norm": float(np.mean(root_vel_norm)) if root_vel_norm.size else 0.0,
        "max_root_velocity_norm": float(np.max(root_vel_norm)) if root_vel_norm.size else 0.0,
        "foot_contact_switch_count": int(switch_count),
        "foot_contact_consistency": float(np.clip(foot_contact_consistency, 0.0, 1.0)),
        "foot_sliding": float(foot_sliding),
    }


def compute_first_second_stability(buffer: EvaluationBuffer, control_dt: float) -> dict:
    T = buffer.num_steps()
    if T == 0:
        return {}
    n = max(1, min(T, int(round(1.0 / control_dt))))
    root_pos = np.stack(buffer._tracked_root_pos[:n], axis=0)
    contacts = buffer._foot_contacts[:n]
    foot_names = sorted(set().union(*[set(item.keys()) for item in contacts]) if contacts else set())

    diag = {
        "num_steps": int(n),
        "min_base_height": float(np.min(root_pos[:, 2])),
        "mean_base_height": float(np.mean(root_pos[:, 2])),
        "max_base_height": float(np.max(root_pos[:, 2])),
        "max_abs_roll": float(np.max(np.abs(np.asarray(buffer._base_roll[:n], dtype=np.float32)))),
        "max_abs_pitch": float(np.max(np.abs(np.asarray(buffer._base_pitch[:n], dtype=np.float32)))),
        "max_qvel_norm": float(np.max(np.asarray(buffer._qvel_norm[:n], dtype=np.float32))),
        "mean_qvel_norm": float(np.mean(np.asarray(buffer._qvel_norm[:n], dtype=np.float32))),
        "max_root_velocity_norm": float(
            np.max(np.asarray(buffer._root_velocity_norm[:n], dtype=np.float32))
        ),
        "mean_root_velocity_norm": float(
            np.mean(np.asarray(buffer._root_velocity_norm[:n], dtype=np.float32))
        ),
    }
    for foot in foot_names:
        vals = [1.0 if item.get(foot, False) else 0.0 for item in contacts]
        diag[f"{foot}_foot_contact_ratio"] = float(np.mean(vals)) if vals else 0.0
    if {"left", "right"}.issubset(set(foot_names)):
        both = [
            1.0
            if item.get("left", False) and item.get("right", False)
            else 0.0
            for item in contacts
        ]
        none = [
            1.0
            if not item.get("left", False) and not item.get("right", False)
            else 0.0
            for item in contacts
        ]
        diag["both_feet_contact_ratio"] = float(np.mean(both))
        diag["no_foot_contact_ratio"] = float(np.mean(none))
    return diag
