"""Validate the middle-layer TransitionPlanner decisions against the configured fallbacks."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import yaml

from middle_architecture.gmt_motion_adapter import GmtMotionAdapter
from middle_architecture.matcher import MatchResult
from middle_architecture.robot_state import RobotState
from middle_architecture.transition_builder import TransitionBuilder
from middle_architecture.transition_planner import TransitionPlanner
from middle_architecture.transition_registry import TransitionRegistry
from task_plan.skill_registry import SkillRegistry


HARNESS_CONFIG = "configs/harness.yaml"
SKILLS_CONFIG = "configs/skills.yaml"
TRANSITIONS_CONFIG = "configs/transitions.yaml"


def state_from_motion_frame(motion, frame_idx, root_lin_vel=None, dof_vel=None):
    q_xyzw = motion.root_rot[frame_idx]
    return RobotState(
        root_pos=motion.root_pos[frame_idx].copy(),
        root_quat=np.array([q_xyzw[3], q_xyzw[0], q_xyzw[1], q_xyzw[2]], dtype=np.float32),
        dof_pos=motion.dof_pos[frame_idx].copy(),
        root_lin_vel=np.asarray(root_lin_vel if root_lin_vel is not None else [0.0, 0.0, 0.0], dtype=np.float32),
        root_ang_vel=np.zeros(3, dtype=np.float32),
        dof_vel=np.asarray(
            dof_vel if dof_vel is not None else np.zeros(motion.dof_pos.shape[1]), dtype=np.float32
        ),
    )


def match_for(skill_spec, motion, start_frame=0):
    return MatchResult(
        motion_path=skill_spec.motion_file,
        start_frame=start_frame,
        end_frame=motion.num_frames,
        score=0.0,
        reason="validate_transition_planner",
    )


with open(HARNESS_CONFIG, "r", encoding="utf-8") as f:
    harness_config = yaml.safe_load(f)
planner_config = harness_config["transition_planner"]
assert planner_config.get("enabled") is True, "transition_planner should be enabled in harness.yaml"

skill_registry = SkillRegistry.from_yaml(SKILLS_CONFIG)
transition_registry = TransitionRegistry.from_yaml(TRANSITIONS_CONFIG)
motion_adapter = GmtMotionAdapter(harness_config["motion_assets"]["root"])

kick_spec = skill_registry.get("kick_leg")
kick_motion = motion_adapter.load(kick_spec.motion_file)
crouch_spec = skill_registry.get("crouch_down")
crouch_motion = motion_adapter.load(crouch_spec.motion_file)
stand_up_spec = skill_registry.get("stand_up")
stand_up_motion = motion_adapter.load(stand_up_spec.motion_file)
walk_motion = motion_adapter.load(skill_registry.get("walk_forward").motion_file)
stand_bridge_spec = skill_registry.get(planner_config["stand_ready_skill"])
stand_motion = motion_adapter.load(stand_bridge_spec.motion_file)

stand_ready_state = state_from_motion_frame(stand_motion, int(stand_bridge_spec.default_start_frame))
walking_state = state_from_motion_frame(
    walk_motion, walk_motion.num_frames // 2, root_lin_vel=[0.6, 0.0, 0.0]
)

pairs = [
    ("walk_forward", "kick_leg", kick_spec, kick_motion),
    ("kick_leg", "crouch_down", crouch_spec, crouch_motion),
    ("crouch_down", "stand_up", stand_up_spec, stand_up_motion),
]

# 1. Disabled planner returns every fallback spec untouched.
disabled_planner = TransitionPlanner(skill_registry, motion_adapter, {**planner_config, "enabled": False})
for from_skill, to_skill, next_spec, next_motion in pairs:
    fallback = transition_registry.get(from_skill, to_skill)
    plan = disabled_planner.plan(fallback, walking_state, next_spec, next_motion, match_for(next_spec, next_motion))
    assert plan.spec is fallback, (from_skill, to_skill)
    assert plan.decision == "fallback_config", plan.decision
print("1. disabled planner returns fallback specs unchanged")

planner = TransitionPlanner(skill_registry, motion_adapter, planner_config)

# 2. Configured interpolation transitions pass through unchanged.
for from_skill, to_skill, next_spec, next_motion in pairs[1:]:
    fallback = transition_registry.get(from_skill, to_skill)
    plan = planner.plan(fallback, stand_ready_state, next_spec, next_motion, match_for(next_spec, next_motion))
    assert plan.decision == "keep_config_interpolation", plan.decision
    assert plan.spec is fallback, (from_skill, to_skill)
    assert plan.spec.mode == "interpolation"
    assert plan.spec.interpolation_mode == fallback.interpolation_mode
    assert plan.spec.hermite_tension == fallback.hermite_tension
    assert plan.spec.num_frames == fallback.num_frames
print("2. interpolation transitions pass through unchanged")

# 3. A mid-gait walking state keeps the configured bridge.
bridge_fallback = transition_registry.get("walk_forward", "kick_leg")
plan = planner.plan(bridge_fallback, walking_state, kick_spec, kick_motion, match_for(kick_spec, kick_motion))
assert plan.decision == "keep_bridge_not_stand_ready", plan.decision
assert plan.spec is bridge_fallback
failed = [k for k, c in plan.diagnostics["criteria"].items() if not c["passed"]]
assert "root_lin_vel_norm" in failed, failed
print(f"3. walking state keeps bridge; failed criteria: {failed}")

# 4. A stand-ready state skips the bridge for a short Hermite interpolation.
plan = planner.plan(bridge_fallback, stand_ready_state, kick_spec, kick_motion, match_for(kick_spec, kick_motion))
for name, check in plan.diagnostics["criteria"].items():
    print(f"   {name}: value={check['value']:.4f} threshold={check['threshold']:.4f} passed={check['passed']}")
assert plan.decision == "skip_bridge_near_stand_ready", plan.decision
short_interp = planner_config["short_interp"]
assert plan.spec.mode == "interpolation"
assert plan.spec.interpolation_mode == short_interp["interpolation_mode"]
assert plan.spec.num_frames == int(short_interp["num_frames"])
assert plan.spec.hermite_tension == float(short_interp["hermite_tension"])
assert bridge_fallback.mode == "bridge", "fallback spec must not be mutated"
print("4. stand-ready state skips bridge with short hermite interpolation")

# 5. The derived spec builds a valid transition segment.
builder = TransitionBuilder(motion_source=skill_registry, motion_adapter=motion_adapter)
segment = builder.build_transition(plan.spec, stand_ready_state, kick_spec, target_frame_idx=0)
frames = segment.reference_frames
assert frames.dof_pos.shape[0] == int(short_interp["num_frames"]), frames.dof_pos.shape
assert np.allclose(frames.dof_pos[0], stand_ready_state.dof_pos, atol=1e-4)
assert np.allclose(frames.dof_pos[-1], kick_motion.dof_pos[0], atol=1e-4)
print("5. derived spec builds a 24-frame hermite segment with matching endpoints")

print("\nAll assertions passed.")

