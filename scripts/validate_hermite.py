"""Validate hermite_interpolate_reference_frames and compute_transition_metrics.
No MuJoCo or torch required.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from middle_architecture.robot_state import KinematicFrame, ReferenceFrames
from middle_architecture.reference_ops import (
    interpolate_reference_frames,
    hermite_interpolate_reference_frames,
    compute_transition_metrics,
)

n_dof = 23
num_frames = 40
fps = 30.0

p0 = np.array([0.0, 0.0, 0.8], dtype=np.float32)
p1 = np.array([1.0, 0.5, 0.85], dtype=np.float32)
q_id = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)

start = KinematicFrame(root_pos=p0, root_quat=q_id, dof_pos=np.zeros(n_dof, dtype=np.float32))
end = KinematicFrame(root_pos=p1, root_quat=q_id, dof_pos=np.ones(n_dof, dtype=np.float32) * 0.5)

v0 = np.array([0.3, 0.1, 0.0], dtype=np.float32)
v1 = np.array([0.2, 0.2, 0.0], dtype=np.float32)
dof_v0 = np.zeros(n_dof, dtype=np.float32)
dof_v1 = np.zeros(n_dof, dtype=np.float32)

# Linear baseline
linear_frames = interpolate_reference_frames(start, end, num_frames=num_frames, fps=fps)

# Hermite
hermite_frames = hermite_interpolate_reference_frames(
    start=start, start_lin_vel=v0, start_dof_vel=dof_v0,
    target_frame=end, target_lin_vel=v1, target_dof_vel=dof_v1,
    num_frames=num_frames, fps=fps,
)

# Boundary conditions: first and last frames should equal start/end positions
np.testing.assert_allclose(hermite_frames.root_pos[0], p0, atol=1e-5, err_msg="Hermite start pos mismatch")
np.testing.assert_allclose(hermite_frames.root_pos[-1], p1, atol=1e-5, err_msg="Hermite end pos mismatch")
np.testing.assert_allclose(hermite_frames.dof_pos[0], start.dof_pos, atol=1e-5, err_msg="Hermite start dof mismatch")
np.testing.assert_allclose(hermite_frames.dof_pos[-1], end.dof_pos, atol=1e-5, err_msg="Hermite end dof mismatch")

# C1 continuity check: velocity at t=0 should approximate v0
dt = 1.0 / fps
T_total = num_frames / fps
vel_at_start = (hermite_frames.root_pos[1] - hermite_frames.root_pos[0]) / dt
vel_at_end = (hermite_frames.root_pos[-1] - hermite_frames.root_pos[-2]) / dt
# The Hermite tangent at t=0 is m0 = v0 * T_total, in normalized alpha space.
# Velocity in world-time is m0/T_total = v0. Check within tolerance.
np.testing.assert_allclose(vel_at_start, v0, atol=0.1, err_msg="Hermite C1 start velocity mismatch")
np.testing.assert_allclose(vel_at_end, v1, atol=0.1, err_msg="Hermite C1 end velocity mismatch")

print("Hermite boundary and C1 continuity checks: PASSED")

# Compute transition metrics for both
# Use a fake 5-frame next-skill segment
next_frames = ReferenceFrames(
    fps=fps,
    root_pos=np.tile(p1, (5, 1)).astype(np.float32),
    root_rot=np.tile(q_id, (5, 1)).astype(np.float32),
    dof_pos=np.tile(end.dof_pos, (5, 1)).astype(np.float32),
)

linear_metrics = compute_transition_metrics(linear_frames, next_frames, "linear")
hermite_metrics = compute_transition_metrics(hermite_frames, next_frames, "hermite")

print("\nTransition metrics comparison:")
print(f"{'Metric':<25} {'Linear':>12} {'Hermite':>12}")
print("-" * 52)
for attr in ["seam_vel_delta", "seam_accel_delta", "peak_jerk", "mean_jerk", "auj"]:
    lv = getattr(linear_metrics, attr)
    hv = getattr(hermite_metrics, attr)
    print(f"  {attr:<23} {lv:>12.4f} {hv:>12.4f}")

assert linear_metrics.interpolation_mode == "linear"
assert hermite_metrics.interpolation_mode == "hermite"
assert hermite_metrics.num_frames == num_frames
assert linear_metrics.num_frames == num_frames

# Tension parameter test: use large start velocity (post-kick scenario) to show
# that tension=0.5 reduces peak jerk while preserving endpoint positions.
v0_large = np.array([3.0, 0.5, 0.0], dtype=np.float32)   # large kick follow-through velocity
v1_large = np.array([0.0, 0.0, 0.0], dtype=np.float32)    # crouch entry (nearly stationary)

hermite_full = hermite_interpolate_reference_frames(
    start=start, start_lin_vel=v0_large, start_dof_vel=dof_v0,
    target_frame=end, target_lin_vel=v1_large, target_dof_vel=dof_v1,
    num_frames=num_frames, fps=fps, tension=1.0,
)
hermite_tight = hermite_interpolate_reference_frames(
    start=start, start_lin_vel=v0_large, start_dof_vel=dof_v0,
    target_frame=end, target_lin_vel=v1_large, target_dof_vel=dof_v1,
    num_frames=num_frames, fps=fps, tension=0.5,
)
full_metrics = compute_transition_metrics(hermite_full, next_frames, "hermite")
tight_metrics = compute_transition_metrics(hermite_tight, next_frames, "hermite")

np.testing.assert_allclose(hermite_tight.root_pos[0], p0, atol=1e-5, err_msg="Tension 0.5: start pos mismatch")
np.testing.assert_allclose(hermite_tight.root_pos[-1], p1, atol=1e-5, err_msg="Tension 0.5: end pos mismatch")
np.testing.assert_allclose(hermite_full.root_pos[0], p0, atol=1e-5, err_msg="Tension 1.0: start pos mismatch")
np.testing.assert_allclose(hermite_full.root_pos[-1], p1, atol=1e-5, err_msg="Tension 1.0: end pos mismatch")
assert tight_metrics.peak_jerk < full_metrics.peak_jerk, (
    f"tension=0.5 must reduce peak jerk for high-velocity case: "
    f"got {tight_metrics.peak_jerk:.4f} vs {full_metrics.peak_jerk:.4f}"
)
print(f"\nTension comparison — high-velocity start (tension=0.5 vs tension=1.0):")
print(f"  peak_jerk: {tight_metrics.peak_jerk:.4f} < {full_metrics.peak_jerk:.4f}  ✓")
print(f"  endpoints preserved at both tension values  ✓")

print("\nAll assertions passed.")
