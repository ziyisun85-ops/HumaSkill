"""Validate that kick_leg can keep its preparation frames under global pose_search."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import yaml

from middle_architecture.gmt_motion_adapter import load_gmt_motion
from middle_architecture.matcher import MotionMatcher
from middle_architecture.robot_state import MatchConfig, RobotState
from task_plan.skill_registry import SkillRegistry


HARNESS_CONFIG = "configs/harness.yaml"
SKILLS_CONFIG = "configs/skills.yaml"


with open(HARNESS_CONFIG, "r", encoding="utf-8") as f:
    harness_config = yaml.safe_load(f)

registry = SkillRegistry.from_yaml(SKILLS_CONFIG)
skill_spec = registry.get("kick_leg")
motion = load_gmt_motion(skill_spec.motion_file, name="kick_leg")

matcher = MotionMatcher(
    MatchConfig(
        mode=harness_config["matching"]["mode"],
        search_window=int(harness_config["matching"]["search_window"]),
        score_weights=harness_config["matching"]["score_weights"],
    )
)

q_xyzw = motion.root_rot[40]
robot_state = RobotState(
    root_pos=motion.root_pos[40].copy(),
    root_quat=[q_xyzw[3], q_xyzw[0], q_xyzw[1], q_xyzw[2]],
    dof_pos=motion.dof_pos[40].copy(),
    root_lin_vel=[0.0, 0.0, 0.0],
    root_ang_vel=[0.0, 0.0, 0.0],
    dof_vel=[0.0] * motion.dof_pos.shape[1],
)

result = matcher.select(robot_state, skill_spec, motion)
print("kick_leg matching result:", result)
assert result.start_frame == 0, (
    "kick_leg should preserve the motion preparation frames instead of "
    f"pose-searching into frame {result.start_frame}"
)
assert result.reason == "static_skill_spec_match", result.reason

print("\nAll assertions passed.")

