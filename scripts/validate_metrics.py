"""Validate evaluation.py metric computation without MuJoCo or torch."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from middle_architecture.evaluation import EvaluationBuffer, compute_segment_metrics

T = 100
control_dt = 0.02
fps = 30.0
n_dof = 23

rng = np.random.default_rng(0)

# Ground-truth trajectories
t_arr = np.arange(T) * control_dt
ref_pos = np.stack([np.sin(t_arr), np.cos(t_arr), 0.8 + 0.05 * np.sin(2 * t_arr)], axis=1).astype(np.float32)
ref_dof = (rng.uniform(-0.3, 0.3, (T, n_dof))).astype(np.float32)
ref_vel = np.diff(ref_pos, axis=0, prepend=ref_pos[:1]) / control_dt
ref_quat = np.zeros((T, 4), dtype=np.float32)
ref_quat[:, 3] = 1.0  # identity quaternion xyzw

# Tracked with small noise
noise_pos = rng.normal(0, 0.01, (T, 3)).astype(np.float32)
tracked_pos = ref_pos + noise_pos
tracked_dof = ref_dof + rng.normal(0, 0.02, (T, n_dof)).astype(np.float32)
tracked_vel = ref_vel + rng.normal(0, 0.05, (T, 3)).astype(np.float32)
# wxyz identity
tracked_quat_wxyz = np.zeros((T, 4), dtype=np.float32)
tracked_quat_wxyz[:, 0] = 1.0

buf = EvaluationBuffer()
for i in range(T):
    buf.record(
        step=i,
        tracked_root_pos=tracked_pos[i],
        tracked_root_quat_wxyz=tracked_quat_wxyz[i],
        tracked_dof_pos=tracked_dof[i],
        tracked_lin_vel=tracked_vel[i],
        ref_root_pos=ref_pos[i],
        ref_root_rot_xyzw=ref_quat[i],
        ref_dof_pos=ref_dof[i],
        ref_lin_vel=ref_vel[i],
    )

metrics = compute_segment_metrics(buf, control_dt=control_dt, fall_min_height=0.20, reference_fps=fps)

print("SegmentMetrics:")
import dataclasses
for k, v in dataclasses.asdict(metrics).items():
    print(f"  {k}: {v}")

assert metrics.num_steps == T, f"Expected {T} steps, got {metrics.num_steps}"
assert metrics.maje > 0, "MAJE should be positive with noise"
assert metrics.maje < 0.5, f"MAJE too high: {metrics.maje}"
assert metrics.root_height_error >= 0, "Height error must be non-negative"
assert metrics.root_pos_error >= 0, "Pos error must be non-negative"
assert metrics.root_rot_error >= 0, "Rot error must be non-negative"
assert metrics.velocity_error >= 0, "Vel error must be non-negative"
assert metrics.success_margin > 0, f"Expected positive success_margin (robot above 0.8m), got {metrics.success_margin}"
assert isinstance(metrics.phase_lag_frame, int), "phase_lag_frame must be int"

# JSON serialization
import json
d = dataclasses.asdict(metrics)
json_str = json.dumps(d)
assert "maje" in json_str

print("\nAll assertions passed.")
