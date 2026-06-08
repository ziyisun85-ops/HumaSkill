"""Validate that skill clips are reanchored after transition execution.

The orchestrator should not anchor the next skill to the pre-transition state.
This MuJoCo-free regression test uses a fake runner whose transition call moves
the robot far away; the following skill reference must start at that moved state.
"""
import math
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

from middle_architecture.harness_orchestrator import HarnessOrchestrator
from middle_architecture.robot_state import ReferenceFrames, RobotState
from middle_architecture.transition_registry import TransitionSpec
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


class _FakeRunner:
    def __init__(self):
        self.call_count = 0
        self.recorded_first_roots = []
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

    def track(self, reference_frames, future_reference_frames=None):
        self.call_count += 1
        self.recorded_first_roots.append(reference_frames.root_pos[0].copy())
        if self.call_count == 1:
            self.state = RobotState(
                root_pos=np.array([1.0, 0.0, 0.8], dtype=np.float32),
                root_quat=_wxyz_from_yaw(0.0),
                dof_pos=np.zeros(23, dtype=np.float32),
                root_lin_vel=np.zeros(3, dtype=np.float32),
                root_ang_vel=np.zeros(3, dtype=np.float32),
                dof_vel=np.zeros(23, dtype=np.float32),
            )
        elif self.call_count == 2:
            self.state = RobotState(
                root_pos=np.array([10.0, 0.0, 0.8], dtype=np.float32),
                root_quat=_wxyz_from_yaw(1.0),
                dof_pos=np.zeros(23, dtype=np.float32),
                root_lin_vel=np.zeros(3, dtype=np.float32),
                root_ang_vel=np.zeros(3, dtype=np.float32),
                dof_vel=np.zeros(23, dtype=np.float32),
            )
        return _FakeTrackResult()


class _FakeSkillRegistry:
    def __init__(self):
        self._skills = {
            "a": SkillSpec(name="a", motion_file="a.pkl"),
            "b": SkillSpec(name="b", motion_file="b.pkl"),
        }

    def get(self, name):
        return self._skills[name]


class _FakeTransitionRegistry:
    def get(self, from_skill, to_skill):
        return TransitionSpec(
            from_skill=from_skill,
            to_skill=to_skill,
            mode="interpolation",
            num_frames=2,
        )


class _FakeMotionAdapter:
    def load(self, motion_file):
        return SimpleNamespace(
            fps=30.0,
            num_frames=4,
            root_pos=np.zeros((4, 3), dtype=np.float32),
            root_rot=np.tile(
                np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32),
                (4, 1),
            ),
            dof_pos=np.zeros((4, 23), dtype=np.float32),
            local_body_pos=None,
        )


runner = _FakeRunner()
orchestrator = HarnessOrchestrator(
    runner=runner,
    skill_registry=_FakeSkillRegistry(),
    transition_registry=_FakeTransitionRegistry(),
    motion_adapter=_FakeMotionAdapter(),
    config={
        "runtime": {"output_root": "outputs/test_orchestrator_reanchor"},
        "reference_contract": {
            "reanchor_skill_clip": True,
            "root_reference_mode": "absolute_root",
            "reanchor_yaw_only": True,
        },
    },
)

plan = SimpleNamespace(
    task_id="fake_reanchor_timing",
    sequence=[
        SimpleNamespace(skill="a", duration=None),
        SimpleNamespace(skill="b", duration=None),
    ],
)

orchestrator.execute(plan)

assert len(runner.recorded_first_roots) == 3, runner.recorded_first_roots
second_skill_first_root = runner.recorded_first_roots[2]
expected = np.array([10.0, 0.0, 0.8], dtype=np.float32)

print("Second skill first reference root:", second_skill_first_root.tolist())
np.testing.assert_allclose(second_skill_first_root, expected, atol=1e-5)

print("\nAll assertions passed.")
