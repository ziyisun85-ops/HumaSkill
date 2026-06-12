"""Validate M6 visual smoothness metrics without MuJoCo."""
import dataclasses
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np

from middle_architecture.evaluation import EvaluationBuffer, compute_segment_metrics
from middle_architecture.reference_ops import compute_transition_metrics
from middle_architecture.robot_state import ReferenceFrames


def _identity_xyzw(n: int) -> np.ndarray:
    q = np.zeros((n, 4), dtype=np.float32)
    q[:, 3] = 1.0
    return q


T = 6
control_dt = 0.02
buf = EvaluationBuffer()
for i in range(T):
    foot_contact = {"left": bool(i < 4), "right": bool(i % 2 == 0)}
    foot_positions = {
        "left": np.array([0.01 * i, 0.1, 0.0], dtype=np.float32),
        "right": np.array([0.0, -0.1, 0.0], dtype=np.float32),
    }
    buf.record(
        step=i,
        tracked_root_pos=np.array([0.01 * i, 0.0, 0.8], dtype=np.float32),
        tracked_root_quat_wxyz=np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32),
        tracked_dof_pos=np.zeros(23, dtype=np.float32),
        tracked_lin_vel=np.array([0.1, 0.0, 0.0], dtype=np.float32),
        ref_root_pos=np.array([0.01 * i, 0.0, 0.8], dtype=np.float32),
        ref_root_rot_xyzw=np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32),
        ref_dof_pos=np.zeros(23, dtype=np.float32),
        ref_lin_vel=np.array([0.1, 0.0, 0.0], dtype=np.float32),
        base_roll=0.01 * i,
        base_pitch=-0.02 * i,
        qvel_norm=0.2 + 0.1 * i,
        root_velocity_norm=0.1,
        foot_contacts=foot_contact,
        foot_positions=foot_positions,
    )

metrics = compute_segment_metrics(buf, control_dt=control_dt, fall_min_height=0.20)
metrics_dict = dataclasses.asdict(metrics)
for key in [
    "max_abs_roll",
    "max_abs_pitch",
    "max_qvel_norm",
    "foot_contact_consistency",
    "foot_contact_switch_count",
    "foot_sliding",
]:
    assert key in metrics_dict, f"missing {key}"
assert metrics.foot_contact_switch_count > 0
assert metrics.foot_sliding > 0.0

transition_frames = ReferenceFrames(
    fps=30.0,
    root_pos=np.array([[0.0, 0.0, 0.8], [0.05, 0.0, 0.8], [0.1, 0.0, 0.8]], dtype=np.float32),
    root_rot=_identity_xyzw(3),
    dof_pos=np.zeros((3, 23), dtype=np.float32),
)
next_skill_frames = ReferenceFrames(
    fps=30.0,
    root_pos=np.array([[0.1, 0.0, 0.8], [0.15, 0.0, 0.8], [0.2, 0.0, 0.8]], dtype=np.float32),
    root_rot=_identity_xyzw(3),
    dof_pos=np.zeros((3, 23), dtype=np.float32),
)
transition_metrics = compute_transition_metrics(transition_frames, next_skill_frames, "hermite")
transition_dict = dataclasses.asdict(transition_metrics)
for key in [
    "root_position_jump",
    "root_yaw_jump_deg",
    "root_height_jump",
    "base_velocity_jump",
    "dof_position_jump_mean",
    "phase_compatibility_score",
]:
    assert key in transition_dict, f"missing {key}"
assert transition_metrics.root_position_jump < 1e-6
assert transition_metrics.phase_compatibility_score > 0.9

print("Segment visual metrics:", {k: metrics_dict[k] for k in metrics_dict if "foot" in k})
print("Transition visual metrics:", transition_dict)
print("\nAll assertions passed.")

