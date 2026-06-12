from typing import Dict, Optional
import json
from pathlib import Path

import numpy as np

from low_level_execution.gmt_tracking_runner import _ReferenceSampler
from middle_architecture.feature_extraction import populate_skillmotion_features
from middle_architecture.gmt_motion_adapter import GMTMotion, GmtMotionAdapter
from middle_architecture.robot_state import ReferenceFrames
from middle_architecture.skill_motion import (
    SkillMotion,
    SkillMotionBoundaries,
    SkillMotionRecoveryMeta,
    SkillMotionRole,
    SkillMotionSource,
    SkillMotionTrackingMeta,
)
from middle_architecture.source_adapters.base import SourceAdapter
from task_plan.skill_registry import SkillRegistry, SkillSpec


ROLE_ASSIGNMENTS = {
    "walk_forward": ("locomotion", "normal", None),
    "kick_leg": ("locomotion", "dynamic", None),
    "crouch_down": ("locomotion", "normal", None),
    "stand_up": ("stabilization", "normal", None),
    "stable_stand_bridge": ("stabilization", "safe_reentry", "stand_ready"),
    "crouchwalk_bridge": ("stabilization", "normal", None),
}


def qpos_from_gmt_motion(motion: GMTMotion) -> np.ndarray:
    return np.concatenate(
        [
            np.asarray(motion.root_pos, dtype=np.float32),
            np.asarray(motion.root_rot, dtype=np.float32),
            np.asarray(motion.dof_pos, dtype=np.float32),
        ],
        axis=1,
    ).astype(np.float32)


def qvel_from_gmt_motion(motion: GMTMotion) -> np.ndarray:
    reference = ReferenceFrames(
        fps=float(motion.fps),
        root_pos=np.asarray(motion.root_pos, dtype=np.float32),
        root_rot=np.asarray(motion.root_rot, dtype=np.float32),
        dof_pos=np.asarray(motion.dof_pos, dtype=np.float32),
        local_body_pos=(
            np.asarray(motion.local_body_pos, dtype=np.float32)
            if motion.local_body_pos is not None
            else None
        ),
    )
    sampler = _ReferenceSampler(reference)
    return np.concatenate(
        [sampler.root_vel, sampler.root_ang_vel, sampler.dof_vel],
        axis=1,
    ).astype(np.float32)


class QposClipAdapter(SourceAdapter):
    def __init__(self, motions_root: str = ".") -> None:
        self.motion_adapter = GmtMotionAdapter(motions_root)

    def convert(
        self,
        skill_spec: SkillSpec,
        role: Optional[SkillMotionRole] = None,
    ) -> SkillMotion:
        motion = self.motion_adapter.load(skill_spec.motion_file)
        qpos = qpos_from_gmt_motion(motion)
        qvel = qvel_from_gmt_motion(motion)
        if role is None:
            role = role_for_skill(skill_spec.name)

        target_safe_state = role.target_safe_state
        recovery = SkillMotionRecoveryMeta(
            enabled=role.recovery_tag in {"safe_reentry", "high_risk"},
            recommended_reentry_skill=skill_spec.name if role.recovery_tag == "safe_reentry" else None,
            notes=(
                f"target_safe_state={target_safe_state}"
                if target_safe_state is not None
                else ""
            ),
        )
        skill_motion = SkillMotion(
            name=skill_spec.name,
            fps=float(motion.fps),
            dof=int(motion.dof_pos.shape[1]),
            qpos=qpos,
            qvel=qvel,
            source=SkillMotionSource(
                type="qpos_clip",
                original_asset=skill_spec.motion_file,
                adapter="QposClipAdapter",
                metadata={"gmt_motion_path": motion.path},
            ),
            role=role,
            boundaries=SkillMotionBoundaries(
                default_start_frame=int(skill_spec.default_start_frame),
                default_end_frame=skill_spec.default_end_frame,
            ),
            local_body_pos=(
                np.asarray(motion.local_body_pos, dtype=np.float32)
                if motion.local_body_pos is not None
                else None
            ),
            features={
                "placeholder": np.zeros((motion.num_frames,), dtype=np.float32),
            },
            semantic_metadata={
                "description": skill_spec.description,
                "registry_motion_file": skill_spec.motion_file,
                "registry_matching_mode": skill_spec.matching_mode,
            },
            tracking=SkillMotionTrackingMeta(
                primary_tracker="gmt_g1",
                tracker_spec="configs/trackers/gmt_g1.yaml",
                playability={},
            ),
            recovery=recovery,
            tracker_audit={"gmt_g1": {"status": "not_run", "source": "qpos_clip_adapter"}},
        )
        return populate_skillmotion_features(skill_motion)


def role_for_skill(skill_name: str) -> SkillMotionRole:
    skill_type, recovery_tag, target_safe_state = ROLE_ASSIGNMENTS.get(
        skill_name, ("locomotion", "normal", None)
    )
    return SkillMotionRole(
        skill_type=skill_type,
        recovery_tag=recovery_tag,
        target_safe_state=target_safe_state,
    )


def convert_registry(skills_yaml: str, output_root: str, motions_root: str = ".") -> Dict[str, SkillMotion]:
    from middle_architecture.skill_motion import save_skillmotion

    registry = SkillRegistry.from_yaml(skills_yaml)
    adapter = QposClipAdapter(motions_root=motions_root)
    converted = {}
    for skill_name in sorted(registry.skills.keys()):
        spec = registry.get(skill_name)
        motion = adapter.convert(spec)
        audit_path = Path(output_root) / skill_name / "tracker_audit.json"
        if audit_path.exists():
            try:
                motion.tracker_audit = json.loads(
                    audit_path.read_text(encoding="utf-8") or "{}"
                )
            except Exception:
                pass
        save_skillmotion(motion, output_root)
        converted[skill_name] = motion
    return converted
