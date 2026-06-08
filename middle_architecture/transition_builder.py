from dataclasses import replace

import numpy as np

from middle_architecture.gmt_motion_adapter import get_kinematic_frame
from middle_architecture.reference_ops import (
    _derive_frame_velocity,
    compute_transition_metrics,
    concat_reference_frames,
    hermite_interpolate_reference_frames,
    interpolate_reference_frames,
    reanchor_reference_frames,
    reanchor_kinematic_frame,
    slice_motion_to_reference_frames,
)
from middle_architecture.robot_state import KinematicFrame, ReferenceSegment, RobotState
from task_plan.skill_registry import SkillRegistry


def _derive_angular_velocity_at_frame(motion, frame_idx: int):
    fps = float(motion.fps)
    n = motion.num_frames
    if frame_idx <= 0:
        q0 = motion.root_rot[0]
        q1 = motion.root_rot[min(1, n - 1)]
    elif frame_idx >= n - 1:
        q0 = motion.root_rot[-2]
        q1 = motion.root_rot[-1]
    else:
        q0 = motion.root_rot[frame_idx - 1]
        q1 = motion.root_rot[frame_idx + 1]
        fps = fps / 2.0
    # Rotation from q0 to q1: dq = q1 * q0_conj
    q0_conj = np.array([-q0[0], -q0[1], -q0[2], q0[3]], dtype=np.float32)
    x1, y1, z1, w1 = q1
    x2, y2, z2, w2 = q0_conj
    dq = np.array([
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
    ], dtype=np.float32)
    dq = dq / max(float(np.linalg.norm(dq)), 1e-9)
    w_comp = float(np.clip(dq[3], -1.0, 1.0))
    sin_theta = float(np.sqrt(max(0.0, 1.0 - w_comp ** 2)))
    angle = 2.0 * float(np.arccos(abs(w_comp)))
    if sin_theta > 1e-5:
        axis = dq[:3] / sin_theta
    else:
        axis = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    ang_vel = axis * (angle * fps)
    return ang_vel.astype(np.float32), None


def _wxyz_from_xyzw(q):
    q = np.asarray(q, dtype=np.float32)
    return np.array([q[3], q[0], q[1], q[2]], dtype=np.float32)


def _zero_velocity_state_from_kinematic_frame(frame: KinematicFrame) -> RobotState:
    return RobotState(
        root_pos=np.asarray(frame.root_pos, dtype=np.float32),
        root_quat=_wxyz_from_xyzw(frame.root_quat),
        dof_pos=np.asarray(frame.dof_pos, dtype=np.float32),
        root_lin_vel=np.zeros(3, dtype=np.float32),
        root_ang_vel=np.zeros(3, dtype=np.float32),
        dof_vel=np.zeros_like(np.asarray(frame.dof_pos, dtype=np.float32)),
    )


def _frame_from_reference_frames(frames, frame_idx: int) -> KinematicFrame:
    local_body_pos = None
    if frames.local_body_pos is not None:
        local_body_pos = frames.local_body_pos[frame_idx].copy()
    return KinematicFrame(
        root_pos=frames.root_pos[frame_idx].copy(),
        root_quat=frames.root_rot[frame_idx].copy(),
        dof_pos=frames.dof_pos[frame_idx].copy(),
        local_body_pos=local_body_pos,
    )


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
        target_frame_idx = int(next_skill_spec.default_start_frame)
        target_frame = get_kinematic_frame(next_motion, target_frame_idx)
        num_frames = spec.num_frames or 20
        frames = self._build_interp_frames(
            spec, current_state, target_frame, next_motion, target_frame_idx, num_frames, next_motion.fps,
        )
        next_skill_frames = slice_motion_to_reference_frames(next_motion, target_frame_idx, min(target_frame_idx + 5, next_motion.num_frames))
        trans_metrics = compute_transition_metrics(frames, next_skill_frames, spec.interpolation_mode)
        return ReferenceSegment(
            segment_id=f"transition_{spec.from_skill}_to_{spec.to_skill}",
            segment_type="transition",
            skill_name=None,
            reference_frames=frames,
            transition_type="interpolation",
            from_skill=spec.from_skill,
            to_skill=spec.to_skill,
            reason=spec.reason,
            metadata={"num_frames": num_frames, "transition_metrics": trans_metrics},
        )

    def build_bridge_transition(self, spec, current_state, next_skill_spec) -> ReferenceSegment:
        if not spec.bridge_skill:
            raise ValueError("bridge transition requires bridge_skill")

        bridge_skill_spec = self._get_skill_spec(spec.bridge_skill)
        bridge_motion = self.motion_adapter.load(bridge_skill_spec.motion_file)
        bridge_start = int(bridge_skill_spec.default_start_frame)
        bridge_end = bridge_skill_spec.default_end_frame or bridge_motion.num_frames
        bridge_entry = get_kinematic_frame(bridge_motion, bridge_start)
        anchored_bridge_entry = reanchor_kinematic_frame(bridge_entry, current_state)
        bridge_anchor_state = _zero_velocity_state_from_kinematic_frame(anchored_bridge_entry)
        bridge_frames = reanchor_reference_frames(
            slice_motion_to_reference_frames(bridge_motion, bridge_start, bridge_end),
            bridge_anchor_state,
            {"root_reference_mode": "absolute_root", "reanchor_yaw_only": True},
        )
        bridge_exit = _frame_from_reference_frames(bridge_frames, -1)

        next_motion = self.motion_adapter.load(next_skill_spec.motion_file)
        next_entry_idx = int(next_skill_spec.default_start_frame)
        target_entry = get_kinematic_frame(next_motion, next_entry_idx)

        pre_frames = spec.pre_bridge_interp_frames or 0
        post_frames = spec.post_bridge_interp_frames or 0
        parts = []
        if pre_frames > 0:
            parts.append(
                self._build_interp_frames(
                    spec, current_state, bridge_entry, bridge_motion, bridge_start,
                    pre_frames, bridge_motion.fps,
                )
            )
        parts.append(bridge_frames)
        if post_frames > 0:
            parts.append(
                self._build_interp_frames(
                    spec, bridge_exit, target_entry, next_motion, next_entry_idx,
                    post_frames, bridge_motion.fps,
                )
            )

        frames = concat_reference_frames(parts)
        next_skill_frames = slice_motion_to_reference_frames(next_motion, next_entry_idx, min(next_entry_idx + 5, next_motion.num_frames))
        trans_metrics = compute_transition_metrics(frames, next_skill_frames, spec.interpolation_mode)
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
                "transition_metrics": trans_metrics,
            },
        )

    def build_bridge_body(self, spec, current_state, next_skill_spec) -> ReferenceSegment:
        if not spec.bridge_skill:
            raise ValueError("bridge transition requires bridge_skill")

        bridge_skill_spec = self._get_skill_spec(spec.bridge_skill)
        bridge_motion = self.motion_adapter.load(bridge_skill_spec.motion_file)
        bridge_start = int(bridge_skill_spec.default_start_frame)
        bridge_end = bridge_skill_spec.default_end_frame or bridge_motion.num_frames
        bridge_entry = get_kinematic_frame(bridge_motion, bridge_start)
        anchored_bridge_entry = reanchor_kinematic_frame(bridge_entry, current_state)
        bridge_anchor_state = _zero_velocity_state_from_kinematic_frame(anchored_bridge_entry)
        bridge_frames = reanchor_reference_frames(
            slice_motion_to_reference_frames(bridge_motion, bridge_start, bridge_end),
            bridge_anchor_state,
            {"root_reference_mode": "absolute_root", "reanchor_yaw_only": True},
        )

        pre_frames = spec.pre_bridge_interp_frames or 0
        parts = []
        if pre_frames > 0:
            parts.append(
                self._build_interp_frames(
                    spec, current_state, bridge_entry, bridge_motion, bridge_start,
                    pre_frames, bridge_motion.fps,
                )
            )
        parts.append(bridge_frames)
        frames = concat_reference_frames(parts)

        return ReferenceSegment(
            segment_id=f"transition_{spec.from_skill}_to_{spec.to_skill}_body",
            segment_type="transition",
            skill_name=None,
            reference_frames=frames,
            source_motion_path=bridge_skill_spec.motion_file,
            start_frame=bridge_start,
            end_frame=bridge_end,
            transition_type="bridge_body",
            from_skill=spec.from_skill,
            to_skill=spec.to_skill,
            reason=spec.reason,
            metadata={
                "bridge_skill": spec.bridge_skill,
                "pre_bridge_interp_frames": pre_frames,
                "bridge_reanchored_to_pre_target": True,
            },
        )

    def build_bridge_post(self, spec, bridge_exit_state, next_skill_spec):
        post_frames = spec.post_bridge_interp_frames or 0
        if post_frames <= 0:
            return None

        bridge_skill_spec = self._get_skill_spec(spec.bridge_skill)
        bridge_motion = self.motion_adapter.load(bridge_skill_spec.motion_file)
        next_motion = self.motion_adapter.load(next_skill_spec.motion_file)
        next_entry_idx = int(next_skill_spec.default_start_frame)
        target_entry = get_kinematic_frame(next_motion, next_entry_idx)

        post_spec = spec
        if (
            spec.interpolation_mode == "linear"
            and hasattr(bridge_exit_state, "root_lin_vel")
            and hasattr(bridge_exit_state, "dof_vel")
            and hasattr(bridge_exit_state, "root_ang_vel")
        ):
            post_spec = replace(spec, interpolation_mode="hermite", hermite_tension=1.0)

        frames = self._build_interp_frames(
            post_spec, bridge_exit_state, target_entry, next_motion, next_entry_idx,
            post_frames, bridge_motion.fps,
        )
        next_skill_frames = slice_motion_to_reference_frames(next_motion, next_entry_idx, min(next_entry_idx + 5, next_motion.num_frames))
        trans_metrics = compute_transition_metrics(frames, next_skill_frames, post_spec.interpolation_mode)

        return ReferenceSegment(
            segment_id=f"transition_{spec.from_skill}_to_{spec.to_skill}_post",
            segment_type="transition",
            skill_name=None,
            reference_frames=frames,
            transition_type="bridge_post",
            from_skill=spec.from_skill,
            to_skill=spec.to_skill,
            reason=spec.reason,
            metadata={
                "post_bridge_interp_frames": post_frames,
                "post_start": "real_robot_state",
                "post_interpolation_mode": post_spec.interpolation_mode,
                "post_hermite_tension": post_spec.hermite_tension,
                "transition_metrics": trans_metrics,
            },
        )

    def _build_interp_frames(self, spec, current_state, target_kinematic_frame, target_motion, target_frame_idx, num_frames, fps):
        target_kinematic_frame = reanchor_kinematic_frame(target_kinematic_frame, current_state)
        if spec.interpolation_mode == "hermite":
            start_lin_vel = getattr(current_state, "root_lin_vel", np.zeros(3, dtype=np.float32))
            start_dof_vel = getattr(current_state, "dof_vel", np.zeros(target_motion.dof_pos.shape[1], dtype=np.float32))
            start_ang_vel = getattr(current_state, "root_ang_vel", None)
            target_lin_vel, target_dof_vel = _derive_frame_velocity(target_motion, target_frame_idx)
            target_ang_vel, _ = _derive_angular_velocity_at_frame(target_motion, target_frame_idx)
            return hermite_interpolate_reference_frames(
                start=current_state,
                start_lin_vel=start_lin_vel,
                start_dof_vel=start_dof_vel,
                target_frame=target_kinematic_frame,
                target_lin_vel=target_lin_vel,
                target_dof_vel=target_dof_vel,
                num_frames=num_frames,
                fps=fps,
                tension=spec.hermite_tension,
                start_ang_vel=start_ang_vel,
                target_ang_vel=target_ang_vel,
            )
        return interpolate_reference_frames(
            current_state, target_kinematic_frame, num_frames=num_frames, fps=fps
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
