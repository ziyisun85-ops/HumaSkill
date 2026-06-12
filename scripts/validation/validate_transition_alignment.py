"""Validate transition reference alignment at bridge seams.

This script is intentionally MuJoCo-free. It checks that bridge transition
reference frames preserve root XY/yaw continuity when the current robot state
is offset from the raw bridge motion coordinates.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np

from middle_architecture.gmt_motion_adapter import GmtMotionAdapter
from middle_architecture.reference_ops import _yaw_from_xyzw
from middle_architecture.robot_state import RobotState
from middle_architecture.transition_builder import TransitionBuilder
from middle_architecture.transition_registry import TransitionRegistry
from task_plan.skill_registry import SkillRegistry


def _wrap_angle(angle: float) -> float:
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def _wxyz_from_yaw(yaw: float) -> np.ndarray:
    half = 0.5 * yaw
    return np.array([math.cos(half), 0.0, 0.0, math.sin(half)], dtype=np.float32)


skills = SkillRegistry.from_yaml("configs/skills.yaml")
transitions = TransitionRegistry.from_yaml("configs/transitions.yaml")
adapter = GmtMotionAdapter("assets/motions")
builder = TransitionBuilder(skills, adapter)

current_yaw = 1.2
current_state = RobotState(
    root_pos=np.array([5.0, -2.0, 0.82], dtype=np.float32),
    root_quat=_wxyz_from_yaw(current_yaw),
    dof_pos=np.zeros(23, dtype=np.float32),
    root_lin_vel=np.zeros(3, dtype=np.float32),
    root_ang_vel=np.zeros(3, dtype=np.float32),
    dof_vel=np.zeros(23, dtype=np.float32),
)

spec = transitions.get("walk_forward", "kick_leg")
segment = builder.build_bridge_body(spec, current_state)
frames = segment.reference_frames

pre_frames = int(spec.pre_bridge_interp_frames or 0)
assert pre_frames > 0, "This validation expects a bridge pre-interp section"
assert frames.root_pos.shape[0] > pre_frames, "Bridge body must include post-pre bridge frames"

pre_end_idx = pre_frames - 1
bridge_start_idx = pre_frames

xy_jump = float(
    np.linalg.norm(frames.root_pos[bridge_start_idx, :2] - frames.root_pos[pre_end_idx, :2])
)
yaw_pre = _yaw_from_xyzw(frames.root_rot[pre_end_idx])
yaw_bridge = _yaw_from_xyzw(frames.root_rot[bridge_start_idx])
yaw_jump_deg = abs(math.degrees(_wrap_angle(yaw_bridge - yaw_pre)))

print("Bridge body seam alignment:")
print(f"  xy_jump: {xy_jump:.6f} m")
print(f"  yaw_jump: {yaw_jump_deg:.6f} deg")

assert xy_jump < 0.05, f"Expected bridge body XY continuity, got {xy_jump:.6f} m"
assert yaw_jump_deg < 3.0, f"Expected bridge body yaw continuity, got {yaw_jump_deg:.6f} deg"

print("\nAll assertions passed.")

