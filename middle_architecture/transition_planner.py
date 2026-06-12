import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict

import numpy as np

from middle_architecture.gmt_motion_adapter import get_kinematic_frame
from middle_architecture.transition_registry import TransitionSpec


@dataclass
class TransitionPlan:
    spec: TransitionSpec
    decision: str
    reason: str
    diagnostics: Dict[str, Any] = field(default_factory=dict)


def _roll_pitch_from_wxyz(q) -> tuple:
    w, x, y, z = (float(v) for v in np.asarray(q, dtype=np.float32))
    roll = float(np.arctan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y)))
    pitch = float(np.arcsin(np.clip(2.0 * (w * y - z * x), -1.0, 1.0)))
    return roll, pitch


class TransitionPlanner:
    """Decides at runtime how to connect previous_skill -> next_skill.

    The configured TransitionSpec from configs/transitions.yaml is the
    fallback/default. The planner may replace a bridge transition with a
    short Hermite interpolation when the live RobotState is already near
    the stable stand-ready pose, so the long bridge body adds nothing.
    """

    def __init__(self, skill_registry, motion_adapter, config: dict):
        self.skill_registry = skill_registry
        self.motion_adapter = motion_adapter
        self.config = config or {}

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("enabled", False))

    def plan(
        self, fallback_spec, robot_state, next_skill_spec, next_motion, match
    ) -> TransitionPlan:
        if not self.enabled:
            return TransitionPlan(
                spec=fallback_spec,
                decision="fallback_config",
                reason="transition_planner_disabled",
            )
        if fallback_spec.mode == "interpolation":
            return TransitionPlan(
                spec=fallback_spec,
                decision="keep_config_interpolation",
                reason="configured_interpolation_passed_through",
            )
        if fallback_spec.mode != "bridge":
            return TransitionPlan(
                spec=fallback_spec,
                decision="fallback_config",
                reason=f"unknown_mode_{fallback_spec.mode}",
            )
        return self._plan_bridge(fallback_spec, robot_state, next_motion, match)

    def _plan_bridge(self, fallback_spec, robot_state, next_motion, match) -> TransitionPlan:
        thresholds = self.config.get("skip_bridge", {})
        stand_skill_name = self.config.get("stand_ready_skill", "stable_stand_bridge")
        stand_skill = self.skill_registry.get(stand_skill_name)
        stand_motion = self.motion_adapter.load(stand_skill.motion_file)
        stand_frame = get_kinematic_frame(stand_motion, int(stand_skill.default_start_frame))

        dof_pos = np.asarray(robot_state.dof_pos, dtype=np.float32)
        roll, pitch = _roll_pitch_from_wxyz(robot_state.root_quat)
        target_entry_dof = np.asarray(next_motion.dof_pos[int(match.start_frame)], dtype=np.float32)

        criteria = {
            "dof_pos_mean_diff": (
                float(np.mean(np.abs(dof_pos - stand_frame.dof_pos))),
                float(thresholds.get("max_dof_pos_mean_diff", 0.15)),
            ),
            "root_height_diff": (
                abs(float(robot_state.root_pos[2]) - float(stand_frame.root_pos[2])),
                float(thresholds.get("max_root_height_diff", 0.08)),
            ),
            "roll_pitch": (
                max(abs(roll), abs(pitch)),
                float(thresholds.get("max_roll_pitch", 0.15)),
            ),
            "root_lin_vel_norm": (
                float(np.linalg.norm(np.asarray(robot_state.root_lin_vel, dtype=np.float32))),
                float(thresholds.get("max_root_lin_vel", 0.25)),
            ),
            "dof_vel_norm": (
                float(np.linalg.norm(np.asarray(robot_state.dof_vel, dtype=np.float32))),
                float(thresholds.get("max_dof_vel_norm", 2.5)),
            ),
            "target_entry_dof_diff": (
                float(np.mean(np.abs(dof_pos - target_entry_dof))),
                float(thresholds.get("max_target_entry_dof_diff", 0.30)),
            ),
        }
        checks = {
            name: {"value": value, "threshold": threshold, "passed": value <= threshold}
            for name, (value, threshold) in criteria.items()
        }
        diagnostics = {
            "stand_ready_skill": stand_skill_name,
            "stand_ready_frame": int(stand_skill.default_start_frame),
            "target_entry_frame": int(match.start_frame),
            "criteria": checks,
        }

        failed = [name for name, check in checks.items() if not check["passed"]]
        if failed:
            return TransitionPlan(
                spec=fallback_spec,
                decision="keep_bridge_not_stand_ready",
                reason="failed_criteria:" + ",".join(failed),
                diagnostics=diagnostics,
            )

        short_interp = self.config.get("short_interp", {})
        derived_spec = dataclasses.replace(
            fallback_spec,
            mode="interpolation",
            interpolation_mode=str(short_interp.get("interpolation_mode", "hermite")),
            num_frames=int(short_interp.get("num_frames", 24)),
            hermite_tension=float(short_interp.get("hermite_tension", 1.0)),
        )
        return TransitionPlan(
            spec=derived_spec,
            decision="skip_bridge_near_stand_ready",
            reason="robot_near_stable_stand_ready_short_hermite_into_next_skill",
            diagnostics=diagnostics,
        )
