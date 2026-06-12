from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import yaml

from middle_architecture.gmt_motion_adapter import GMTMotion


SCHEMA_VERSION = 1
SOURCE_TYPES = {
    "qpos_clip",
    "rl_rollout",
    "diffusion_generated",
    "teleop_demo",
    "manual_clip",
    "optimized_motion",
}
SKILL_TYPES = {
    "locomotion",
    "upper_body_gesture",
    "stabilization",
    "recovery",
    "transition",
    "full_body",
}
RECOVERY_TAGS = {"normal", "dynamic", "high_risk", "safe_reentry"}


@dataclass
class SkillMotionSource:
    type: str
    original_asset: str
    adapter: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillMotionRole:
    skill_type: str
    recovery_tag: str = "normal"
    target_safe_state: Optional[str] = None


@dataclass
class SkillMotionBoundaries:
    default_start_frame: int = 0
    default_end_frame: Optional[int] = None
    entry_window_start: Optional[int] = None
    entry_window_end: Optional[int] = None
    exit_window_start: Optional[int] = None
    exit_window_end: Optional[int] = None
    entry_window_low_confidence: bool = False
    exit_window_low_confidence: bool = False


@dataclass
class SkillMotionTrackingMeta:
    primary_tracker: str = "gmt_g1"
    tracker_spec: str = "configs/trackers/gmt_g1.yaml"
    playability: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillMotionRecoveryMeta:
    enabled: bool = False
    recommended_reentry_skill: Optional[str] = None
    notes: str = ""


@dataclass
class SkillMotion:
    """Standard CHOREO phase-1 motion object.

    Stored conventions:
    - `qpos` shape is `(N, 7 + dof)` and stores root position (meters),
      root quaternion in GMT pkl `xyzw` order, then GMT G1 joint positions.
    - `qvel` shape is `(N, 6 + dof)` and stores world root linear velocity,
      root angular velocity, then joint velocity, all derived with the GMT
      runner's window-19 smoothing convention.
    - `local_body_pos` is optional `(N, bodies, 3)` source kinematic data.
    - YAML metadata stores only metadata and relative paths, never array data.
    """

    name: str
    fps: float
    dof: int
    qpos: np.ndarray
    qvel: np.ndarray
    source: SkillMotionSource
    role: SkillMotionRole
    boundaries: SkillMotionBoundaries
    local_body_pos: Optional[np.ndarray] = None
    features: Dict[str, np.ndarray] = field(default_factory=dict)
    semantic_metadata: Dict[str, Any] = field(default_factory=dict)
    tracking: SkillMotionTrackingMeta = field(default_factory=SkillMotionTrackingMeta)
    recovery: SkillMotionRecoveryMeta = field(default_factory=SkillMotionRecoveryMeta)
    tracker_audit: Dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION
    robot: str = "g1"
    root_quat_order: str = "xyzw"
    dof_order: str = "gmt_g1_23"
    units: str = "meters_radians"

    @property
    def num_frames(self) -> int:
        return int(self.qpos.shape[0])

    @property
    def root_pos(self) -> np.ndarray:
        return self.qpos[:, 0:3]

    @property
    def root_rot(self) -> np.ndarray:
        return self.qpos[:, 3:7]

    @property
    def dof_pos(self) -> np.ndarray:
        return self.qpos[:, 7:]

    def to_gmt_motion(self) -> GMTMotion:
        return GMTMotion(
            name=self.name,
            path=f"skillmotion:{self.name}",
            fps=float(self.fps),
            root_pos=self.root_pos.astype(np.float32).copy(),
            root_rot=self.root_rot.astype(np.float32).copy(),
            dof_pos=self.dof_pos.astype(np.float32).copy(),
            local_body_pos=(
                self.local_body_pos.astype(np.float32).copy()
                if self.local_body_pos is not None
                else None
            ),
            num_frames=self.num_frames,
        )


class SkillMotionLibraryAdapter:
    """GMTMotion-compatible adapter backed by a SkillMotion library.

    Existing middle-layer code asks a motion adapter to `load(motion_file)`.
    During the flag-gated SkillMotion path we keep that call shape and resolve
    the registry motion file back to the per-skill SkillMotion entry.
    """

    def __init__(self, library_root: str, skill_registry) -> None:
        self.library_root = library_root
        self.skill_registry = skill_registry
        self._cache: Dict[str, SkillMotion] = {}
        self._motion_file_to_skill = {}
        for name, spec in sorted(skill_registry.skills.items()):
            self._motion_file_to_skill.setdefault(spec.motion_file, name)

    def load_skillmotion(self, skill_name: str) -> SkillMotion:
        if skill_name not in self._cache:
            self._cache[skill_name] = load_skillmotion(self.library_root, skill_name)
        return self._cache[skill_name]

    def load_for_skill(self, skill_name: str) -> GMTMotion:
        return self.load_skillmotion(skill_name).to_gmt_motion()

    def load(self, motion_file: str) -> GMTMotion:
        skill_name = self._motion_file_to_skill.get(motion_file)
        if skill_name is None:
            raise KeyError(
                f"No SkillMotion entry mapped from registry motion file: {motion_file}"
            )
        return self.load_for_skill(skill_name)

    def motion_source_block(self, skill_name: str) -> Dict[str, Any]:
        motion = self.load_skillmotion(skill_name)
        return {
            "type": "skillmotion",
            "library_entry": motion.name,
            "source_type": motion.source.type,
            "source_asset": motion.source.original_asset,
            "role": {
                "skill_type": motion.role.skill_type,
                "recovery_tag": motion.role.recovery_tag,
                "target_safe_state": motion.role.target_safe_state,
            },
        }


def _require(mapping: Dict[str, Any], key: str, metadata_path: Path) -> Any:
    if key not in mapping:
        raise ValueError(f"{metadata_path}: missing required key '{key}'")
    return mapping[key]


def _validate_enum(value: str, allowed, metadata_path: Path, key: str) -> None:
    if value not in allowed:
        raise ValueError(
            f"{metadata_path}: invalid {key} '{value}', expected one of {sorted(allowed)}"
        )


def _array_path(entry_dir: Path, arrays: Dict[str, Any], key: str, metadata_path: Path) -> Path:
    rel = _require(arrays, key, metadata_path)
    if not isinstance(rel, str):
        raise ValueError(f"{metadata_path}: arrays.{key} must be a relative path string")
    path = entry_dir / rel
    if not path.exists():
        raise ValueError(f"{metadata_path}: arrays.{key} missing file {path}")
    return path


def _metadata_for_motion(motion: SkillMotion) -> Dict[str, Any]:
    arrays = {
        "qpos": "qpos.npy",
        "qvel": "qvel.npy",
        "features": "features.npz",
        "tracker_audit": "tracker_audit.json",
    }
    if motion.local_body_pos is not None:
        arrays["local_body_pos"] = "local_body_pos.npy"
    return {
        "schema_version": int(motion.schema_version),
        "identity": {
            "name": motion.name,
            "robot": motion.robot,
            "fps": float(motion.fps),
            "num_frames": int(motion.num_frames),
            "dof": int(motion.dof),
        },
        "source": asdict(motion.source),
        "role": asdict(motion.role),
        "boundaries": asdict(motion.boundaries),
        "semantics": dict(motion.semantic_metadata),
        "tracking": asdict(motion.tracking),
        "recovery": asdict(motion.recovery),
        "trajectory": {
            "root_quat_order": motion.root_quat_order,
            "dof_order": motion.dof_order,
            "units": motion.units,
            "qpos_shape": [int(v) for v in motion.qpos.shape],
            "qvel_shape": [int(v) for v in motion.qvel.shape],
            "local_body_pos_shape": (
                [int(v) for v in motion.local_body_pos.shape]
                if motion.local_body_pos is not None
                else None
            ),
        },
        "arrays": arrays,
    }


def save_skillmotion(motion: SkillMotion, library_root: str) -> Path:
    _validate_motion_object(motion, Path(library_root) / motion.name / "metadata.yaml")
    entry_dir = Path(library_root) / motion.name
    entry_dir.mkdir(parents=True, exist_ok=True)

    np.save(entry_dir / "qpos.npy", np.asarray(motion.qpos, dtype=np.float32))
    np.save(entry_dir / "qvel.npy", np.asarray(motion.qvel, dtype=np.float32))
    np.savez(entry_dir / "features.npz", **motion.features)
    if motion.local_body_pos is not None:
        np.save(entry_dir / "local_body_pos.npy", np.asarray(motion.local_body_pos, dtype=np.float32))
    (entry_dir / "tracker_audit.json").write_text(
        json.dumps(motion.tracker_audit, indent=2), encoding="utf-8"
    )
    metadata = _metadata_for_motion(motion)
    (entry_dir / "metadata.yaml").write_text(
        yaml.safe_dump(metadata, sort_keys=False), encoding="utf-8"
    )
    return entry_dir


def load_skillmotion(library_root: str, name: str) -> SkillMotion:
    entry_dir = Path(library_root) / name
    metadata_path = entry_dir / "metadata.yaml"
    if not metadata_path.exists():
        raise ValueError(f"{metadata_path}: metadata.yaml does not exist")
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = yaml.safe_load(f)
    if not isinstance(metadata, dict):
        raise ValueError(f"{metadata_path}: metadata must be a mapping")

    schema_version = int(_require(metadata, "schema_version", metadata_path))
    if schema_version != SCHEMA_VERSION:
        raise ValueError(
            f"{metadata_path}: unsupported schema_version {schema_version}, expected {SCHEMA_VERSION}"
        )

    identity = _require(metadata, "identity", metadata_path)
    source_raw = _require(metadata, "source", metadata_path)
    role_raw = _require(metadata, "role", metadata_path)
    boundaries_raw = _require(metadata, "boundaries", metadata_path)
    trajectory = _require(metadata, "trajectory", metadata_path)
    arrays = _require(metadata, "arrays", metadata_path)

    if not isinstance(identity, dict):
        raise ValueError(f"{metadata_path}: identity must be a mapping")
    if not isinstance(source_raw, dict):
        raise ValueError(f"{metadata_path}: source must be a mapping")
    if not isinstance(role_raw, dict):
        raise ValueError(f"{metadata_path}: role must be a mapping")
    if not isinstance(boundaries_raw, dict):
        raise ValueError(f"{metadata_path}: boundaries must be a mapping")
    if not isinstance(trajectory, dict):
        raise ValueError(f"{metadata_path}: trajectory must be a mapping")
    if not isinstance(arrays, dict):
        raise ValueError(f"{metadata_path}: arrays must be a mapping")

    source_type = str(_require(source_raw, "type", metadata_path))
    skill_type = str(_require(role_raw, "skill_type", metadata_path))
    recovery_tag = str(role_raw.get("recovery_tag", "normal"))
    _validate_enum(source_type, SOURCE_TYPES, metadata_path, "source.type")
    _validate_enum(skill_type, SKILL_TYPES, metadata_path, "role.skill_type")
    _validate_enum(recovery_tag, RECOVERY_TAGS, metadata_path, "role.recovery_tag")

    qpos = np.load(_array_path(entry_dir, arrays, "qpos", metadata_path)).astype(np.float32)
    qvel = np.load(_array_path(entry_dir, arrays, "qvel", metadata_path)).astype(np.float32)
    features_path = _array_path(entry_dir, arrays, "features", metadata_path)
    features_npz = np.load(features_path)
    features = {key: features_npz[key] for key in features_npz.files}
    tracker_audit_path = _array_path(entry_dir, arrays, "tracker_audit", metadata_path)
    tracker_audit = json.loads(tracker_audit_path.read_text(encoding="utf-8") or "{}")

    local_body_pos = None
    if "local_body_pos" in arrays:
        local_body_pos = np.load(
            _array_path(entry_dir, arrays, "local_body_pos", metadata_path)
        ).astype(np.float32)

    dof = int(_require(identity, "dof", metadata_path))
    num_frames = int(_require(identity, "num_frames", metadata_path))
    fps = float(_require(identity, "fps", metadata_path))
    root_quat_order = str(trajectory.get("root_quat_order", "xyzw"))
    dof_order = str(trajectory.get("dof_order", "gmt_g1_23"))
    units = str(trajectory.get("units", "meters_radians"))

    motion = SkillMotion(
        name=str(_require(identity, "name", metadata_path)),
        fps=fps,
        dof=dof,
        qpos=qpos,
        qvel=qvel,
        source=SkillMotionSource(
            type=source_type,
            original_asset=str(_require(source_raw, "original_asset", metadata_path)),
            adapter=str(source_raw.get("adapter", "")),
            metadata=dict(source_raw.get("metadata", {})),
        ),
        role=SkillMotionRole(
            skill_type=skill_type,
            recovery_tag=recovery_tag,
            target_safe_state=role_raw.get("target_safe_state"),
        ),
        boundaries=SkillMotionBoundaries(
            default_start_frame=int(boundaries_raw.get("default_start_frame", 0)),
            default_end_frame=boundaries_raw.get("default_end_frame"),
            entry_window_start=boundaries_raw.get("entry_window_start"),
            entry_window_end=boundaries_raw.get("entry_window_end"),
            exit_window_start=boundaries_raw.get("exit_window_start"),
            exit_window_end=boundaries_raw.get("exit_window_end"),
            entry_window_low_confidence=bool(
                boundaries_raw.get("entry_window_low_confidence", False)
            ),
            exit_window_low_confidence=bool(
                boundaries_raw.get("exit_window_low_confidence", False)
            ),
        ),
        local_body_pos=local_body_pos,
        features=features,
        semantic_metadata=dict(metadata.get("semantics", {})),
        tracking=SkillMotionTrackingMeta(**dict(metadata.get("tracking", {}))),
        recovery=SkillMotionRecoveryMeta(**dict(metadata.get("recovery", {}))),
        tracker_audit=tracker_audit,
        schema_version=schema_version,
        robot=str(identity.get("robot", "g1")),
        root_quat_order=root_quat_order,
        dof_order=dof_order,
        units=units,
    )
    _validate_motion_object(motion, metadata_path)
    return motion


def _validate_motion_object(motion: SkillMotion, metadata_path: Path) -> None:
    _validate_enum(motion.source.type, SOURCE_TYPES, metadata_path, "source.type")
    _validate_enum(motion.role.skill_type, SKILL_TYPES, metadata_path, "role.skill_type")
    _validate_enum(motion.role.recovery_tag, RECOVERY_TAGS, metadata_path, "role.recovery_tag")
    if motion.schema_version != SCHEMA_VERSION:
        raise ValueError(
            f"{metadata_path}: unsupported schema_version {motion.schema_version}, expected {SCHEMA_VERSION}"
        )
    if motion.root_quat_order != "xyzw":
        raise ValueError(f"{metadata_path}: trajectory.root_quat_order must be 'xyzw'")
    if motion.qpos.ndim != 2:
        raise ValueError(f"{metadata_path}: qpos must be 2-D, got shape {motion.qpos.shape}")
    if motion.qvel.ndim != 2:
        raise ValueError(f"{metadata_path}: qvel must be 2-D, got shape {motion.qvel.shape}")
    if motion.qpos.shape[0] != motion.qvel.shape[0]:
        raise ValueError(f"{metadata_path}: qpos/qvel frame counts must match")
    if motion.qpos.shape[0] == 0:
        raise ValueError(f"{metadata_path}: qpos must contain at least one frame")
    expected_qpos_width = 7 + int(motion.dof)
    expected_qvel_width = 6 + int(motion.dof)
    if motion.qpos.shape[1] != expected_qpos_width:
        raise ValueError(
            f"{metadata_path}: qpos width must be {expected_qpos_width}, got {motion.qpos.shape[1]}"
        )
    if motion.qvel.shape[1] != expected_qvel_width:
        raise ValueError(
            f"{metadata_path}: qvel width must be {expected_qvel_width}, got {motion.qvel.shape[1]}"
        )
    if motion.local_body_pos is not None:
        if motion.local_body_pos.ndim != 3 or motion.local_body_pos.shape[0] != motion.qpos.shape[0]:
            raise ValueError(
                f"{metadata_path}: local_body_pos must have shape (N, bodies, 3), got {motion.local_body_pos.shape}"
            )
        if motion.local_body_pos.shape[2] != 3:
            raise ValueError(
                f"{metadata_path}: local_body_pos last dimension must be 3, got {motion.local_body_pos.shape}"
            )
    if motion.boundaries.default_start_frame < 0:
        raise ValueError(f"{metadata_path}: boundaries.default_start_frame must be >= 0")
    if motion.boundaries.default_end_frame is not None:
        motion.boundaries.default_end_frame = int(motion.boundaries.default_end_frame)
        if motion.boundaries.default_end_frame < motion.boundaries.default_start_frame:
            raise ValueError(
                f"{metadata_path}: boundaries.default_end_frame must be >= default_start_frame"
            )
        if motion.boundaries.default_end_frame > motion.num_frames:
            raise ValueError(
                f"{metadata_path}: boundaries.default_end_frame exceeds num_frames"
            )
