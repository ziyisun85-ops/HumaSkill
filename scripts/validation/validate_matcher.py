"""Validate MotionMatcher static and pose_search modes. No MuJoCo or torch required."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import yaml
from middle_architecture.gmt_motion_adapter import load_gmt_motion
from middle_architecture.matcher import MotionMatcher
from middle_architecture.robot_state import MatchConfig, RobotState
from task_plan.skill_registry import SkillRegistry

MOTION_PATH = "assets/motions/basic_walk.pkl"
SKILLS_CONFIG = "configs/skills.yaml"
HARNESS_CONFIG = "configs/harness.yaml"

registry = SkillRegistry.from_yaml(SKILLS_CONFIG)
skill_spec = registry.get("walk_forward")
with open(HARNESS_CONFIG, "r", encoding="utf-8") as f:
    harness_config = yaml.safe_load(f)
score_weights = harness_config.get("matching", {}).get("score_weights")

motion = load_gmt_motion(MOTION_PATH, name="basic_walk")
print(f"Loaded motion: {motion.num_frames} frames @ {motion.fps} fps")

# Build a robot state that exactly matches frame 10 of the motion
probe_frame = 10
n_dof = motion.dof_pos.shape[1]
q_xyzw = motion.root_rot[probe_frame]
robot_state = RobotState(
    root_pos=motion.root_pos[probe_frame].copy(),
    root_quat=np.array([q_xyzw[3], q_xyzw[0], q_xyzw[1], q_xyzw[2]], dtype=np.float32),
    dof_pos=motion.dof_pos[probe_frame].copy(),
    root_lin_vel=np.zeros(3, dtype=np.float32),
    root_ang_vel=np.zeros(3, dtype=np.float32),
    dof_vel=np.zeros(n_dof, dtype=np.float32),
)

# --- Static mode ---
static_matcher = MotionMatcher(match_config=MatchConfig(mode="static"))
static_result = static_matcher.select(robot_state, skill_spec, motion, duration=5.0)
print(f"\nStatic mode: start_frame={static_result.start_frame}, score={static_result.score}, reason={static_result.reason}")
assert static_result.start_frame == int(skill_spec.default_start_frame), "Static must return default_start_frame"
assert static_result.score == 0.0, "Static mode score must be 0.0"
assert static_result.reason == "static_skill_spec_match"

# --- Pose search mode ---
search_window = 20
pose_matcher = MotionMatcher(
    match_config=MatchConfig(
        mode="pose_search",
        search_window=search_window,
        score_weights=score_weights,
    )
)
pose_result = pose_matcher.select(robot_state, skill_spec, motion, duration=5.0)
print(f"Pose search mode: start_frame={pose_result.start_frame}, score={pose_result.score:.4f}, reason={pose_result.reason}")

default_start = int(skill_spec.default_start_frame)
assert default_start <= pose_result.start_frame <= default_start + search_window, (
    f"pose_search start_frame {pose_result.start_frame} outside window [{default_start}, {default_start+search_window}]"
)
assert pose_result.score >= 0.0, "Score must be non-negative"
assert pose_result.reason == "pose_search_match"

# The probe is exactly frame 10 with matching DOF — expect the best frame to be near frame 10
print(f"  Expected best near frame {probe_frame}, got {pose_result.start_frame}")

# Score at frame 10 should be close to 0 (perfect DOF match)
score_at_probe = pose_matcher._pose_score(robot_state, motion, probe_frame, score_weights)
print(f"  Score at probe frame {probe_frame}: {score_at_probe:.6f}")
assert score_at_probe < 1.0, f"Score at exact match frame should be low, got {score_at_probe}"

distant_frame = min(probe_frame + 15, motion.num_frames - 1)
score_at_distant = pose_matcher._pose_score(robot_state, motion, distant_frame, score_weights)
print(f"  Score at distant frame {distant_frame}: {score_at_distant:.6f}")
assert score_at_probe < score_at_distant, (
    f"Known-good frame should score below a distant frame: "
    f"{score_at_probe:.6f} vs {score_at_distant:.6f}"
)

print("\nAll assertions passed.")

