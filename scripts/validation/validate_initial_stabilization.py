"""Validate M5 initial stabilization orchestration without MuJoCo."""
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np

from middle_architecture.harness_orchestrator import HarnessOrchestrator
from middle_architecture.robot_state import RobotState
from task_plan.skill_registry import SkillSpec


def _wxyz_from_yaw(yaw: float) -> np.ndarray:
    half = 0.5 * yaw
    return np.array([math.cos(half), 0.0, 0.0, math.sin(half)], dtype=np.float32)


class _FakeTrackResult:
    success = True
    num_frames = 1
    log_path = None
    video_path = None
    failed_reason = None
    metrics = None
    diagnostics = {
        "first_second_stability": {
            "min_base_height": 0.76,
            "max_abs_pitch": 0.02,
            "max_abs_roll": 0.03,
            "max_qvel_norm": 0.4,
            "max_root_velocity_norm": 0.08,
            "left_foot_contact_ratio": 1.0,
            "right_foot_contact_ratio": 1.0,
        }
    }


class _FakeRunner:
    def __init__(self):
        self.reference_lengths = []
        self.reset_reference_frames = None
        self.control_modes = []
        self.action_ramp_steps = []
        self.state = RobotState(
            root_pos=np.array([0.0, 0.0, 0.8], dtype=np.float32),
            root_quat=_wxyz_from_yaw(0.0),
            dof_pos=np.zeros(23, dtype=np.float32),
            root_lin_vel=np.zeros(3, dtype=np.float32),
            root_ang_vel=np.zeros(3, dtype=np.float32),
            dof_vel=np.zeros(23, dtype=np.float32),
        )

    def initialize(self):
        return None

    def get_robot_state(self):
        return self.state

    def track(
        self,
        reference_frames,
        future_reference_frames=None,
        control_mode="policy",
        action_ramp_steps=0,
    ):
        self.reference_lengths.append(reference_frames.root_pos.shape[0])
        self.control_modes.append(control_mode)
        self.action_ramp_steps.append(action_ramp_steps)
        return _FakeTrackResult()

    def reset_to_reference_frame(self, reference_frames):
        self.reset_reference_frames = reference_frames


class _FakeSkillRegistry:
    def __init__(self):
        self._skills = {
            "walk_forward": SkillSpec(name="walk_forward", motion_file="walk.pkl"),
            "stable_stand_bridge": SkillSpec(name="stable_stand_bridge", motion_file="stand.pkl"),
        }

    def get(self, name):
        return self._skills[name]


class _FakeTransitionRegistry:
    def get(self, from_skill, to_skill):
        raise AssertionError("single-skill plan should not request transitions")


class _FakeMotionAdapter:
    def load(self, motion_file):
        num_frames = 12
        root_pos = np.tile(np.array([0.0, 0.0, 0.8], dtype=np.float32), (num_frames, 1))
        if motion_file == "walk.pkl":
            root_pos[:, 0] = np.linspace(0.0, 0.2, num_frames, dtype=np.float32)
        root_rot = np.tile(np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32), (num_frames, 1))
        return SimpleNamespace(
            fps=30.0,
            num_frames=num_frames,
            root_pos=root_pos,
            root_rot=root_rot,
            dof_pos=np.zeros((num_frames, 23), dtype=np.float32),
            local_body_pos=None,
        )


output_root = Path("outputs/test_initial_stabilization")
runner = _FakeRunner()
orchestrator = HarnessOrchestrator(
    runner=runner,
    skill_registry=_FakeSkillRegistry(),
    transition_registry=_FakeTransitionRegistry(),
    motion_adapter=_FakeMotionAdapter(),
    config={
        "runtime": {"output_root": str(output_root)},
        "reference_contract": {"reanchor_skill_clip": False},
        "initial_stabilization": {
            "enabled": True,
            "stand_ready_skill": "stable_stand_bridge",
            "blend_frames": 3,
            "hold_frames": 4,
            "reset_to_stand_ready": True,
            "action_ramp_frames": 3,
        },
    },
)

plan = SimpleNamespace(
    task_id="fake_initial_stabilization",
    sequence=[SimpleNamespace(skill="walk_forward", duration=None)],
)
results = orchestrator.execute(plan)

assert results[0].segment_type == "stabilization", results[0]
assert results[0].segment_id == "stabilization_000_stand_ready", results[0].segment_id
assert runner.reference_lengths[0] == 7, runner.reference_lengths
assert runner.control_modes[0] == "policy", runner.control_modes
assert runner.action_ramp_steps[0] == 3, runner.action_ramp_steps
assert runner.reset_reference_frames is not None
np.testing.assert_allclose(
    runner.reset_reference_frames.root_pos[0],
    np.array([0.0, 0.0, 0.8], dtype=np.float32),
)

result_json = output_root / plan.task_id / "stabilization_000_stand_ready" / "result.json"
payload = json.loads(result_json.read_text(encoding="utf-8"))
assert "first_second_stability" in payload["diagnostics"], payload

print("Initial stabilization segment:", results[0].segment_id)
print("First-second stability diagnostics:", payload["diagnostics"]["first_second_stability"])
print("\nAll assertions passed.")

