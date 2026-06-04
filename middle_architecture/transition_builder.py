from middle_architecture.gmt_motion_adapter import get_kinematic_frame
from middle_architecture.reference_ops import (
    concat_reference_frames,
    interpolate_reference_frames,
    slice_motion_to_reference_frames,
)
from middle_architecture.robot_state import ReferenceSegment
from task_plan.skill_registry import SkillRegistry


class TransitionBuilder:
    def __init__(self, motion_source, motion_adapter):
        self.motion_source = motion_source
        self.motion_adapter = motion_adapter
        self._fallback_registry = None

    def build_transition(self, transition_spec, current_state, next_skill_spec) -> ReferenceSegment:
        if transition_spec.mode == "interpolation":
            return self.build_interpolation_transition(
                transition_spec, current_state, next_skill_spec
            )
        if transition_spec.mode == "bridge":
            return self.build_bridge_transition(transition_spec, current_state, next_skill_spec)
        raise ValueError(f"Unsupported transition mode: {transition_spec.mode}")

    def build_interpolation_transition(self, spec, current_state, next_skill_spec) -> ReferenceSegment:
        next_motion = self.motion_adapter.load(next_skill_spec.motion_file)
        target_frame = get_kinematic_frame(next_motion, next_skill_spec.default_start_frame)
        num_frames = spec.num_frames or 20
        frames = interpolate_reference_frames(
            current_state,
            target_frame,
            num_frames=num_frames,
            fps=next_motion.fps,
        )
        return ReferenceSegment(
            segment_id=f"transition_{spec.from_skill}_to_{spec.to_skill}",
            segment_type="transition",
            skill_name=None,
            reference_frames=frames,
            transition_type="interpolation",
            from_skill=spec.from_skill,
            to_skill=spec.to_skill,
            reason=spec.reason,
            metadata={"num_frames": num_frames},
        )

    def build_bridge_transition(self, spec, current_state, next_skill_spec) -> ReferenceSegment:
        if not spec.bridge_skill:
            raise ValueError("bridge transition requires bridge_skill")

        bridge_skill_spec = self._get_skill_spec(spec.bridge_skill)
        bridge_motion = self.motion_adapter.load(bridge_skill_spec.motion_file)
        bridge_start = int(bridge_skill_spec.default_start_frame)
        bridge_end = bridge_skill_spec.default_end_frame or bridge_motion.num_frames
        bridge_entry = get_kinematic_frame(bridge_motion, bridge_start)
        bridge_exit = get_kinematic_frame(bridge_motion, bridge_end - 1)

        next_motion = self.motion_adapter.load(next_skill_spec.motion_file)
        target_entry = get_kinematic_frame(next_motion, next_skill_spec.default_start_frame)

        pre_frames = spec.pre_bridge_interp_frames or 0
        post_frames = spec.post_bridge_interp_frames or 0
        parts = []
        if pre_frames > 0:
            parts.append(
                interpolate_reference_frames(
                    current_state,
                    bridge_entry,
                    num_frames=pre_frames,
                    fps=bridge_motion.fps,
                )
            )
        parts.append(slice_motion_to_reference_frames(bridge_motion, bridge_start, bridge_end))
        if post_frames > 0:
            parts.append(
                interpolate_reference_frames(
                    bridge_exit,
                    target_entry,
                    num_frames=post_frames,
                    fps=bridge_motion.fps,
                )
            )

        frames = concat_reference_frames(parts)
        return ReferenceSegment(
            segment_id=f"transition_{spec.from_skill}_to_{spec.to_skill}",
            segment_type="transition",
            skill_name=None,
            reference_frames=frames,
            source_motion_path=bridge_skill_spec.motion_file,
            start_frame=bridge_start,
            end_frame=bridge_end,
            transition_type="bridge",
            from_skill=spec.from_skill,
            to_skill=spec.to_skill,
            reason=spec.reason,
            metadata={
                "bridge_skill": spec.bridge_skill,
                "pre_bridge_interp_frames": pre_frames,
                "post_bridge_interp_frames": post_frames,
                "post_is_kinematic_bridge_exit_to_target_entry": True,
            },
        )

    def _get_skill_spec(self, skill_name):
        if hasattr(self.motion_source, "get"):
            try:
                return self.motion_source.get(skill_name)
            except Exception:
                pass
        if self._fallback_registry is None:
            self._fallback_registry = SkillRegistry.from_yaml("configs/skills.yaml")
        return self._fallback_registry.get(skill_name)
