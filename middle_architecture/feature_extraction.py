from dataclasses import asdict, dataclass
from typing import Dict, Tuple

import numpy as np

from middle_architecture.skill_motion import SkillMotion, SkillMotionBoundaries


@dataclass
class FeatureExtractionConfig:
    foot_body_indices: Tuple[int, int] = (6, 14)  # left/right ankle_roll_link in GMT pkl link_body_list
    foot_height_margin: float = 0.05
    foot_vertical_velocity_threshold: float = 0.30
    stable_root_velocity_threshold: float = 0.25
    stable_dof_velocity_threshold: float = 0.90
    min_stable_window_frames: int = 5
    fallback_window_frames: int = 10


def _yaw_from_xyzw_batch(q: np.ndarray) -> np.ndarray:
    q = np.asarray(q, dtype=np.float32)
    norm = np.clip(np.linalg.norm(q, axis=1, keepdims=True), 1e-9, None)
    q = q / norm
    x = q[:, 0]
    y = q[:, 1]
    z = q[:, 2]
    w = q[:, 3]
    yaw = np.arctan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
    return np.unwrap(yaw).astype(np.float32)


def _rotate_velocity_to_heading_frame(root_vel: np.ndarray, heading: np.ndarray) -> np.ndarray:
    out = np.asarray(root_vel, dtype=np.float32).copy()
    c = np.cos(-heading)
    s = np.sin(-heading)
    x = out[:, 0].copy()
    y = out[:, 1].copy()
    out[:, 0] = c * x - s * y
    out[:, 1] = s * x + c * y
    return out.astype(np.float32)


def _foot_contacts(
    motion: SkillMotion, config: FeatureExtractionConfig
) -> Tuple[np.ndarray, np.ndarray]:
    n = motion.num_frames
    contacts = np.zeros((n, 2), dtype=np.float32)
    confidence = np.zeros((n, 2), dtype=np.float32)
    if motion.local_body_pos is None:
        return contacts, confidence
    local = np.asarray(motion.local_body_pos, dtype=np.float32)
    if local.ndim != 3 or local.shape[0] != n:
        return contacts, confidence

    for col, body_idx in enumerate(config.foot_body_indices):
        if body_idx < 0 or body_idx >= local.shape[1]:
            continue
        z = local[:, body_idx, 2]
        z_min = float(np.min(z))
        height_above_min = z - z_min
        vz = np.zeros_like(z)
        if n > 1:
            vz[:-1] = float(motion.fps) * (z[1:] - z[:-1])
            vz[-1] = vz[-2]
        height_score = 1.0 - height_above_min / max(config.foot_height_margin, 1e-6)
        vel_score = 1.0 - np.abs(vz) / max(config.foot_vertical_velocity_threshold, 1e-6)
        score = np.clip(0.5 * height_score + 0.5 * vel_score, 0.0, 1.0)
        contact = (
            (height_above_min <= config.foot_height_margin)
            & (np.abs(vz) <= config.foot_vertical_velocity_threshold)
        )
        contacts[:, col] = contact.astype(np.float32)
        confidence[:, col] = score.astype(np.float32)
    return contacts, confidence


def _boundary_windows(
    motion: SkillMotion, config: FeatureExtractionConfig
) -> Tuple[SkillMotionBoundaries, np.ndarray, np.ndarray, bool, bool]:
    n = motion.num_frames
    root_vel_norm = np.linalg.norm(motion.qvel[:, 0:3], axis=1)
    dof_vel_norm = np.linalg.norm(motion.qvel[:, 6:], axis=1)
    stable = (
        (root_vel_norm <= config.stable_root_velocity_threshold)
        & (dof_vel_norm <= config.stable_dof_velocity_threshold)
    )

    min_len = int(config.min_stable_window_frames)
    fallback = max(1, min(int(config.fallback_window_frames), n))

    entry_end = 0
    while entry_end < n and stable[entry_end]:
        entry_end += 1
    entry_low = entry_end < min_len
    if entry_low:
        entry_start, entry_end = 0, fallback
    else:
        entry_start = 0

    exit_start = n
    while exit_start > 0 and stable[exit_start - 1]:
        exit_start -= 1
    exit_low = (n - exit_start) < min_len
    if exit_low:
        exit_start, exit_end = max(0, n - fallback), n
    else:
        exit_end = n

    boundaries = SkillMotionBoundaries(
        default_start_frame=motion.boundaries.default_start_frame,
        default_end_frame=motion.boundaries.default_end_frame,
        entry_window_start=int(entry_start),
        entry_window_end=int(entry_end),
        exit_window_start=int(exit_start),
        exit_window_end=int(exit_end),
        entry_window_low_confidence=bool(entry_low),
        exit_window_low_confidence=bool(exit_low),
    )
    return (
        boundaries,
        np.asarray([entry_start, entry_end], dtype=np.int32),
        np.asarray([exit_start, exit_end], dtype=np.int32),
        bool(entry_low),
        bool(exit_low),
    )


def extract_skillmotion_features(
    motion: SkillMotion, config: FeatureExtractionConfig = None
) -> Tuple[Dict[str, np.ndarray], SkillMotionBoundaries, Dict[str, object]]:
    cfg = config or FeatureExtractionConfig()
    qvel = np.asarray(motion.qvel, dtype=np.float32)
    heading = _yaw_from_xyzw_batch(motion.root_rot)
    root_linear_velocity_world = qvel[:, 0:3].astype(np.float32)
    root_angular_velocity = qvel[:, 3:6].astype(np.float32)
    root_linear_velocity_heading = _rotate_velocity_to_heading_frame(
        root_linear_velocity_world, heading
    )
    foot_contacts, foot_contact_confidence = _foot_contacts(motion, cfg)
    (
        boundaries,
        entry_window,
        exit_window,
        entry_low,
        exit_low,
    ) = _boundary_windows(motion, cfg)

    features = {
        "qvel": qvel,
        "root_linear_velocity_world": root_linear_velocity_world,
        "root_linear_velocity_heading": root_linear_velocity_heading,
        "root_angular_velocity": root_angular_velocity,
        "heading": heading,
        "left_foot_contact": foot_contacts[:, 0],
        "right_foot_contact": foot_contacts[:, 1],
        "foot_contact_confidence": foot_contact_confidence,
        "entry_window": entry_window,
        "exit_window": exit_window,
        "entry_window_low_confidence": np.asarray([entry_low], dtype=np.bool_),
        "exit_window_low_confidence": np.asarray([exit_low], dtype=np.bool_),
    }
    metadata = {
        "feature_extraction": {
            "config": asdict(cfg),
            "contact_columns": ["left", "right"],
            "contact_body_indices": list(cfg.foot_body_indices),
            "entry_window_low_confidence": entry_low,
            "exit_window_low_confidence": exit_low,
        }
    }
    return features, boundaries, metadata


def populate_skillmotion_features(
    motion: SkillMotion, config: FeatureExtractionConfig = None
) -> SkillMotion:
    features, boundaries, metadata = extract_skillmotion_features(motion, config=config)
    motion.features = features
    motion.boundaries = boundaries
    semantic = dict(motion.semantic_metadata)
    semantic.update(metadata)
    motion.semantic_metadata = semantic
    return motion
