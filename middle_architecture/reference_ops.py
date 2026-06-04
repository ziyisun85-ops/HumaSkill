from typing import Iterable, Optional

import numpy as np

from middle_architecture.gmt_motion_adapter import GMTMotion
from middle_architecture.robot_state import KinematicFrame, ReferenceFrames, RobotState


def _normalize_quat_xyzw(q: np.ndarray) -> np.ndarray:
    q = np.asarray(q, dtype=np.float32)
    norm = np.linalg.norm(q)
    if norm < 1e-8:
        raise ValueError("zero-length quaternion")
    return q / norm


def _wxyz_to_xyzw(q: np.ndarray) -> np.ndarray:
    q = np.asarray(q, dtype=np.float32)
    return np.array([q[1], q[2], q[3], q[0]], dtype=np.float32)


def _yaw_from_xyzw(q: np.ndarray) -> float:
    q = _normalize_quat_xyzw(q)
    x, y, z, w = q
    return float(np.arctan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z)))


def _quat_mul_xyzw(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    x1, y1, z1, w1 = a
    x2, y2, z2, w2 = b
    ww = (z1 + x1) * (x2 + y2)
    yy = (w1 - y1) * (w2 + z2)
    zz = (w1 + y1) * (w2 - z2)
    xx = ww + yy + zz
    qq = 0.5 * (xx + (z1 - x1) * (x2 - y2))
    w = qq - ww + (z1 - y1) * (y2 - z2)
    x = qq - xx + (x1 + w1) * (x2 + w2)
    y = qq - yy + (w1 - x1) * (y2 + z2)
    z = qq - zz + (z1 + y1) * (w2 - x2)
    return _normalize_quat_xyzw(np.array([x, y, z, w], dtype=np.float32))


def _yaw_quat_xyzw(yaw: float) -> np.ndarray:
    half = 0.5 * yaw
    return np.array([0.0, 0.0, np.sin(half), np.cos(half)], dtype=np.float32)


def _rotate_xy(points: np.ndarray, yaw: float) -> np.ndarray:
    c = np.cos(yaw)
    s = np.sin(yaw)
    rot = np.array([[c, -s], [s, c]], dtype=np.float32)
    out = points.copy()
    out[:, :2] = points[:, :2] @ rot.T
    return out


def _slerp_xyzw(q0: np.ndarray, q1: np.ndarray, t: np.ndarray) -> np.ndarray:
    q0 = _normalize_quat_xyzw(q0)
    q1 = _normalize_quat_xyzw(q1)
    t = np.asarray(t, dtype=np.float32)
    dot = float(np.dot(q0, q1))
    if dot < 0.0:
        q1 = -q1
        dot = -dot
    dot = np.clip(dot, -1.0, 1.0)
    if dot > 0.9995:
        out = q0[None, :] + t[:, None] * (q1 - q0)[None, :]
        out /= np.linalg.norm(out, axis=1, keepdims=True)
        return out.astype(np.float32)

    theta_0 = np.arccos(dot)
    sin_theta_0 = np.sin(theta_0)
    theta = theta_0 * t
    s0 = np.sin(theta_0 - theta) / sin_theta_0
    s1 = np.sin(theta) / sin_theta_0
    return (s0[:, None] * q0[None, :] + s1[:, None] * q1[None, :]).astype(np.float32)


def _as_kinematic_view(frame) -> KinematicFrame:
    if isinstance(frame, KinematicFrame):
        return frame
    if isinstance(frame, RobotState):
        return KinematicFrame(
            root_pos=np.asarray(frame.root_pos, dtype=np.float32),
            root_quat=_wxyz_to_xyzw(frame.root_quat),
            dof_pos=np.asarray(frame.dof_pos, dtype=np.float32),
            local_body_pos=None,
        )
    raise TypeError(f"Unsupported frame type: {type(frame).__name__}")


def slice_motion_to_reference_frames(
    motion: GMTMotion, start_frame: int, end_frame: Optional[int]
) -> ReferenceFrames:
    if end_frame is None:
        end_frame = motion.num_frames
    if start_frame < 0 or end_frame < start_frame or end_frame > motion.num_frames:
        raise ValueError(
            f"Invalid frame range [{start_frame}, {end_frame}) for {motion.num_frames} frames"
        )

    local_body_pos = None
    if motion.local_body_pos is not None:
        local_body_pos = motion.local_body_pos[start_frame:end_frame].copy()
    return ReferenceFrames(
        fps=float(motion.fps),
        root_pos=motion.root_pos[start_frame:end_frame].copy(),
        root_rot=motion.root_rot[start_frame:end_frame].copy(),
        dof_pos=motion.dof_pos[start_frame:end_frame].copy(),
        local_body_pos=local_body_pos,
    )


def interpolate_reference_frames(start, target_frame, num_frames: int, fps: float) -> ReferenceFrames:
    if num_frames <= 0:
        raise ValueError("num_frames must be positive")

    start_frame = _as_kinematic_view(start)
    target = _as_kinematic_view(target_frame)
    alpha = np.linspace(0.0, 1.0, num_frames, dtype=np.float32)

    root_pos = (
        (1.0 - alpha[:, None]) * np.asarray(start_frame.root_pos, dtype=np.float32)[None, :]
        + alpha[:, None] * np.asarray(target.root_pos, dtype=np.float32)[None, :]
    )
    root_rot = _slerp_xyzw(start_frame.root_quat, target.root_quat, alpha)
    dof_pos = (
        (1.0 - alpha[:, None]) * np.asarray(start_frame.dof_pos, dtype=np.float32)[None, :]
        + alpha[:, None] * np.asarray(target.dof_pos, dtype=np.float32)[None, :]
    )

    local_body_pos = None
    if start_frame.local_body_pos is not None and target.local_body_pos is not None:
        local_body_pos = (
            (1.0 - alpha[:, None, None])
            * np.asarray(start_frame.local_body_pos, dtype=np.float32)[None, :, :]
            + alpha[:, None, None] * np.asarray(target.local_body_pos, dtype=np.float32)[None, :, :]
        )
    elif target.local_body_pos is not None:
        local_body_pos = np.repeat(
            np.asarray(target.local_body_pos, dtype=np.float32)[None, :, :],
            num_frames,
            axis=0,
        )

    return ReferenceFrames(
        fps=float(fps),
        root_pos=root_pos.astype(np.float32),
        root_rot=root_rot.astype(np.float32),
        dof_pos=dof_pos.astype(np.float32),
        local_body_pos=local_body_pos.astype(np.float32) if local_body_pos is not None else None,
    )


def concat_reference_frames(list_of_reference_frames: Iterable[ReferenceFrames]) -> ReferenceFrames:
    frames = list(list_of_reference_frames)
    if not frames:
        raise ValueError("Need at least one ReferenceFrames object to concatenate")

    fps = float(frames[0].fps)
    for item in frames:
        if abs(float(item.fps) - fps) > 1e-6:
            raise ValueError(f"Cannot concat ReferenceFrames with different fps: {fps} vs {item.fps}")

    local_body_pos = None
    if all(item.local_body_pos is not None for item in frames):
        local_body_pos = np.concatenate([item.local_body_pos for item in frames], axis=0)

    return ReferenceFrames(
        fps=fps,
        root_pos=np.concatenate([item.root_pos for item in frames], axis=0),
        root_rot=np.concatenate([item.root_rot for item in frames], axis=0),
        dof_pos=np.concatenate([item.dof_pos for item in frames], axis=0),
        local_body_pos=local_body_pos,
    )


def reanchor_reference_frames(reference_frames: ReferenceFrames, current_state: RobotState, mode):
    yaw_only = True
    mode_name = mode
    if isinstance(mode, dict):
        mode_name = mode.get("root_reference_mode", mode.get("mode", "pass_through"))
        yaw_only = bool(mode.get("reanchor_yaw_only", True))

    if mode_name in (None, "pass_through", "root_relative"):
        return reference_frames
    if mode_name not in ("absolute_root", "offset_root_pos"):
        raise ValueError(f"Unsupported reanchor mode: {mode_name}")

    anchored = ReferenceFrames(
        fps=reference_frames.fps,
        root_pos=reference_frames.root_pos.copy(),
        root_rot=reference_frames.root_rot.copy(),
        dof_pos=reference_frames.dof_pos.copy(),
        local_body_pos=reference_frames.local_body_pos.copy()
        if reference_frames.local_body_pos is not None
        else None,
    )
    current_root = np.asarray(current_state.root_pos, dtype=np.float32)
    first_root = anchored.root_pos[0].copy()

    if mode_name == "absolute_root" and yaw_only:
        current_yaw = _yaw_from_xyzw(_wxyz_to_xyzw(current_state.root_quat))
        first_yaw = _yaw_from_xyzw(anchored.root_rot[0])
        delta_yaw = current_yaw - first_yaw
        relative_pos = anchored.root_pos - first_root[None, :]
        anchored.root_pos = _rotate_xy(relative_pos, delta_yaw) + current_root[None, :]
        delta_quat = _yaw_quat_xyzw(delta_yaw)
        anchored.root_rot = np.stack(
            [_quat_mul_xyzw(delta_quat, q) for q in anchored.root_rot], axis=0
        ).astype(np.float32)
    else:
        delta = current_root - first_root
        anchored.root_pos = anchored.root_pos + delta[None, :]
    return anchored
