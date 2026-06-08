"""Validate transition target frame matches the following skill start frame.

The orchestrator must not build a transition to a skill's default frame and then
start the skill from a different pose_search frame. That creates a visible
joint-pose discontinuity at the transition->skill seam.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

from middle_architecture.harness_orchestrator import HarnessOrchestrator
from middle_architecture.robot_state import RobotState
from middle_architecture.transition_registry import TransitionSpec
from task_plan.skill_registry import SkillSpec


class _FakeTrackResult:
    success = True
    num_frames = 1
    log_path = None
    video_path = None
    failed_reason = None
    metrics = None


def _identity_quat_xyzw(num_frames: int) -> np.ndarray:
    q = np.zeros((num_frames, 4), dtype=np.float32)
    q[:, 3] = 1.0
    return q


def _state_for_dof(dof: np.ndarray) -> RobotState:
    return RobotState(
        root_pos=np.array([0.0, 0.0, 0.8], dtype=np.float32),
        root_quat=np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32),
        dof_pos=dof.astype(np.float32).copy(),
        root_lin_vel=np.zeros(3, dtype=np.float32),
        root_ang_vel=np.zeros(3, dtype=np.float32),
        dof_vel=np.zeros_like(dof, dtype=np.float32),
    )


class _FakeRunner:
    def __init__(self, target_dof: np.ndarray):
        self.call_count = 0
        self.state = _state_for_dof(np.zeros(23, dtype=np.float32))
        self.target_dof = target_dof
        self.transition_last_dof = None
        self.transition_future_first_dof = None
        self.second_skill_first_dof = None

    def initialize(self):
        return None

    def get_robot_state(self):
        return self.state

    def track(self, reference_frames, future_reference_frames=None):
        self.call_count += 1
        if self.call_count == 1:
            self.state = _state_for_dof(self.target_dof)
        elif self.call_count == 2:
            self.transition_last_dof = reference_frames.dof_pos[-1].copy()
            if future_reference_frames is not None:
                self.transition_future_first_dof = future_reference_frames.dof_pos[0].copy()
            self.state = _state_for_dof(self.target_dof)
        elif self.call_count == 3:
            self.second_skill_first_dof = reference_frames.dof_pos[0].copy()
        return _FakeTrackResult()


class _FakeSkillRegistry:
    def __init__(self):
        self._skills = {
            "a": SkillSpec(name="a", motion_file="a.pkl", default_start_frame=0),
            "b": SkillSpec(name="b", motion_file="b.pkl", default_start_frame=0),
        }

    def get(self, name):
        return self._skills[name]


class _FakeTransitionRegistry:
    def get(self, from_skill, to_skill):
        return TransitionSpec(
            from_skill=from_skill,
            to_skill=to_skill,
            mode="interpolation",
            num_frames=4,
            interpolation_mode="linear",
        )


class _FakeMotionAdapter:
    def __init__(self, target_frame: int, target_dof: np.ndarray):
        self.target_frame = target_frame
        self.target_dof = target_dof

    def load(self, motion_file):
        num_frames = 12
        dof = np.zeros((num_frames, 23), dtype=np.float32)
        if motion_file == "b.pkl":
            dof[self.target_frame] = self.target_dof
        return SimpleNamespace(
            fps=30.0,
            num_frames=num_frames,
            root_pos=np.tile(np.array([0.0, 0.0, 0.8], dtype=np.float32), (num_frames, 1)),
            root_rot=_identity_quat_xyzw(num_frames),
            dof_pos=dof,
            local_body_pos=None,
        )


target_frame = 5
target_dof = np.linspace(0.1, 1.0, 23, dtype=np.float32)
runner = _FakeRunner(target_dof)
orchestrator = HarnessOrchestrator(
    runner=runner,
    skill_registry=_FakeSkillRegistry(),
    transition_registry=_FakeTransitionRegistry(),
    motion_adapter=_FakeMotionAdapter(target_frame, target_dof),
    config={
        "runtime": {"output_root": "outputs/test_transition_target_match"},
        "matching": {
            "mode": "pose_search",
            "search_window": 10,
            "score_weights": {
                "dof_pos": 1.0,
                "root_quat": 0.0,
                "velocity": 0.0,
                "root_height": 0.0,
            },
        },
        "reference_contract": {"reanchor_skill_clip": False},
    },
)

plan = SimpleNamespace(
    task_id="fake_transition_target_match",
    sequence=[
        SimpleNamespace(skill="a", duration=None),
        SimpleNamespace(skill="b", duration=None),
    ],
)
orchestrator.execute(plan)

print("Transition last DOF mean:", float(np.mean(runner.transition_last_dof)))
print("Transition future first DOF mean:", float(np.mean(runner.transition_future_first_dof)))
print("Second skill first DOF mean:", float(np.mean(runner.second_skill_first_dof)))
np.testing.assert_allclose(runner.transition_last_dof, runner.second_skill_first_dof, atol=1e-6)
np.testing.assert_allclose(
    runner.transition_future_first_dof,
    runner.second_skill_first_dof,
    atol=1e-6,
)

print("\nAll assertions passed.")
