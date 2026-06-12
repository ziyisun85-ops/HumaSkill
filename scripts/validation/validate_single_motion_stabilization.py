"""Validate single-motion runner uses the configured stand-ready stabilization."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np

from scripts.run_single_gmt_motion import build_initial_stabilization_frames
from middle_architecture.robot_state import RobotState


class _FakeAdapter:
    def load(self, motion_file):
        assert motion_file == "assets/motions/walk_stand.pkl"
        root_pos = np.tile(np.array([0.0, 0.0, 0.765], dtype=np.float32), (4, 1))
        root_rot = np.tile(np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32), (4, 1))
        return SimpleNamespace(
            fps=30.0,
            num_frames=4,
            root_pos=root_pos,
            root_rot=root_rot,
            dof_pos=np.full((4, 23), 0.2, dtype=np.float32),
            local_body_pos=None,
        )


class _FakeSkillRegistry:
    def get(self, name):
        assert name == "stable_stand_bridge"
        return SimpleNamespace(
            motion_file="assets/motions/walk_stand.pkl",
            default_start_frame=0,
        )


state = RobotState(
    root_pos=np.array([1.0, 2.0, 1.0], dtype=np.float32),
    root_quat=np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32),
    dof_pos=np.zeros(23, dtype=np.float32),
    root_lin_vel=np.zeros(3, dtype=np.float32),
    root_ang_vel=np.zeros(3, dtype=np.float32),
    dof_vel=np.zeros(23, dtype=np.float32),
)
config = {
    "enabled": True,
    "stand_ready_skill": "stable_stand_bridge",
    "blend_frames": 3,
    "hold_frames": 4,
    "preserve_initial_root_height": False,
    "reset_to_stand_ready": True,
    "action_ramp_frames": 7,
}

frames, runtime = build_initial_stabilization_frames(
    state=state,
    stabilization_config=config,
    skill_registry=_FakeSkillRegistry(),
    motion_adapter=_FakeAdapter(),
)

assert frames is not None
assert frames.root_pos.shape[0] == 7
assert runtime["reset_to_stand_ready"] is True
assert runtime["action_ramp_steps"] == 7
np.testing.assert_allclose(frames.root_pos[0], np.array([1.0, 2.0, 0.765], dtype=np.float32))
np.testing.assert_allclose(frames.root_pos[-1], np.array([1.0, 2.0, 0.765], dtype=np.float32))

print("Single-motion stabilization frames:", frames.root_pos.shape[0])
print("Single-motion stabilization runtime:", runtime)
print("\nAll assertions passed.")

