"""Validate log-only execution monitor and recovery manager behavior."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import yaml

from middle_architecture.execution_monitor import ExecutionMonitor
from middle_architecture.recovery_manager import RecoveryManager
from middle_architecture.robot_state import ReferenceFrames, ReferenceSegment, RobotState
from middle_architecture.skill_motion import SkillMotionLibraryAdapter
from task_plan.skill_registry import SkillRegistry


REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS_CONFIG = REPO_ROOT / "configs" / "harness.yaml"
SKILLS = REPO_ROOT / "configs" / "skills.yaml"
LIBRARY = REPO_ROOT / "skillmotion_library"


with open(HARNESS_CONFIG, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)
monitor_config = config["execution_monitor"]
assert monitor_config["enabled"] is True

segment = ReferenceSegment(
    segment_id="synthetic_failure",
    segment_type="skill",
    skill_name="walk_forward",
    reference_frames=ReferenceFrames(
        fps=30.0,
        root_pos=np.zeros((2, 3), dtype=np.float32),
        root_rot=np.tile(np.asarray([[0.0, 0.0, 0.0, 1.0]], dtype=np.float32), (2, 1)),
        dof_pos=np.zeros((2, 23), dtype=np.float32),
    ),
)
track_result = SimpleNamespace(
    success=False,
    failed_reason="fell",
    metrics=None,
    diagnostics={},
)
final_state = RobotState(
    root_pos=np.asarray([0.0, 0.0, 0.1], dtype=np.float32),
    root_quat=np.asarray([1.0, 0.0, 0.0, 0.0], dtype=np.float32),
    dof_pos=np.zeros(23, dtype=np.float32),
    root_lin_vel=np.zeros(3, dtype=np.float32),
    root_ang_vel=np.zeros(3, dtype=np.float32),
    dof_vel=np.zeros(23, dtype=np.float32),
)

monitor = ExecutionMonitor(monitor_config)
events = monitor.analyze(segment, track_result, final_state)
assert [event.event_type for event in events] == ["fall_detected"], events
assert events[0].severity == "error"
print("synthetic fall_detected event OK")

registry = SkillRegistry.from_yaml(str(SKILLS))
skillmotion_adapter = SkillMotionLibraryAdapter(str(LIBRARY), registry) if LIBRARY.exists() else None
manager = RecoveryManager(monitor_config.get("recovery"), skillmotion_adapter=skillmotion_adapter)
recommendations = manager.recommend(events)
assert recommendations
assert recommendations[0]["action"] == "recommend_reentry"
assert recommendations[0]["execute"] is False
assert recommendations[0]["skill"] == "stable_stand_bridge"
print("synthetic recovery recommendation OK")

warning_metrics = SimpleNamespace(
    success_margin=0.25,
    max_abs_roll=0.1,
    max_abs_pitch=0.1,
    maje=0.05,
)
warning_result = SimpleNamespace(
    success=True,
    failed_reason=None,
    metrics=warning_metrics,
    diagnostics={},
)
events = monitor.analyze(segment, warning_result, final_state)
assert [event.event_type for event in events] == ["low_success_margin"], events
recommendations = manager.recommend(events)
assert recommendations[0]["action"] == "monitor_only"
assert recommendations[0]["execute"] is False
print("warning event remains log-only OK")

print("Execution monitor validation passed.")
