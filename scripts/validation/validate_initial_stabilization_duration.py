"""Validate initial stabilization is short enough to avoid a visible long pause."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import yaml

from middle_architecture.gmt_motion_adapter import load_gmt_motion
from middle_architecture.harness_orchestrator import HarnessOrchestrator
from middle_architecture.robot_state import RobotState
from task_plan.skill_registry import SkillRegistry


HARNESS_CONFIG = "configs/harness.yaml"
SKILLS_CONFIG = "configs/skills.yaml"


class _NoopRunner:
    pass


with open(HARNESS_CONFIG, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

registry = SkillRegistry.from_yaml(SKILLS_CONFIG)


class _MotionAdapter:
    def load(self, motion_file):
        return load_gmt_motion(motion_file, name=Path(motion_file).stem)


state = RobotState(
    root_pos=[0.0, 0.0, 0.8],
    root_quat=[1.0, 0.0, 0.0, 0.0],
    dof_pos=[0.0] * 23,
    root_lin_vel=[0.0, 0.0, 0.0],
    root_ang_vel=[0.0, 0.0, 0.0],
    dof_vel=[0.0] * 23,
)

orchestrator = HarnessOrchestrator(
    runner=_NoopRunner(),
    skill_registry=registry,
    transition_registry=None,
    motion_adapter=_MotionAdapter(),
    config=config,
)

segment = orchestrator._build_initial_stabilization_segment(state)
assert segment is not None, "initial stabilization must remain enabled"

num_frames = int(segment.reference_frames.root_pos.shape[0])
duration_seconds = num_frames / float(segment.reference_frames.fps)
action_ramp_steps = int(segment.metadata["action_ramp_steps"])

print(f"initial stabilization frames={num_frames}, duration={duration_seconds:.3f}s")
print(f"action_ramp_steps={action_ramp_steps}")

assert num_frames <= 60, (
    "initial stabilization should be a short settle-in, not a multi-second pause: "
    f"{num_frames} frames"
)
assert 0 < action_ramp_steps <= 45, action_ramp_steps

print("\nAll assertions passed.")

