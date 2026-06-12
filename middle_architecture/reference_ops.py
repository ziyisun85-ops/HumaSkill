from typing import Iterable, Optional, Tuple

import numpy as np

from middle_architecture.gmt_motion_adapter import GMTMotion
from middle_architecture.robot_state import KinematicFrame, ReferenceFrames, RobotState, TransitionMetrics


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


def _derive_frame_velocity(
    motion: GMTMotion, frame_idx: int
) -> Tuple[np.ndarray, np.ndarray]:
    fps = float(motion.fps)
    n = motion.num_frames
    if n < 2:
        return np.zeros(3, dtype=np.float32), np.zeros(motion.dof_pos.shape[1], dtype=np.float32)
    if frame_idx <= 0:
        root_vel = fps * (motion.root_pos[1] - motion.root_pos[0])
        dof_vel = fps * (motion.dof_pos[1] - motion.dof_pos[0])
    elif frame_idx >= n - 1:
        root_vel = fps * (motion.root_pos[-1] - motion.root_pos[-2])
        dof_vel = fps * (motion.dof_pos[-1] - motion.dof_pos[-2])
    else:
        root_vel = fps * (motion.root_pos[frame_idx + 1] - motion.root_pos[frame_idx - 1]) / 2.0
        dof_vel = fps * (motion.dof_pos[frame_idx + 1] - motion.dof_pos[frame_idx - 1]) / 2.0
    return root_vel.astype(np.float32), dof_vel.astype(np.float32)


def hermite_interpolate_reference_frames(
    start,
    start_lin_vel: np.ndarray,
    start_dof_vel: np.ndarray,
    target_frame,
    target_lin_vel: np.ndarray,
    target_dof_vel: np.ndarray,
    num_frames: int,
    fps: float,
    tension: float = 1.0,
    start_ang_vel: Optional[np.ndarray] = None,
    target_ang_vel: Optional[np.ndarray] = None,
) -> ReferenceFrames:
    if num_frames <= 0:
        raise ValueError("num_frames must be positive")

    s = _as_kinematic_view(start)
    t = _as_kinematic_view(target_frame)
    T = num_frames / fps

    alpha = np.linspace(0.0, 1.0, num_frames, dtype=np.float32)
    a2 = alpha ** 2
    a3 = alpha ** 3

    h00 = 2.0 * a3 - 3.0 * a2 + 1.0
    h10 = a3 - 2.0 * a2 + alpha
    h01 = -2.0 * a3 + 3.0 * a2
    h11 = a3 - a2

    p0 = np.asarray(s.root_pos, dtype=np.float32)
    p1 = np.asarray(t.root_pos, dtype=np.float32)
    m0_pos = np.asarray(start_lin_vel, dtype=np.float32) * T * tension
    m1_pos = np.asarray(target_lin_vel, dtype=np.float32) * T * tension
    root_pos = (
        h00[:, None] * p0[None, :]
        + h10[:, None] * m0_pos[None, :]
        + h01[:, None] * p1[None, :]
        + h11[:, None] * m1_pos[None, :]
    ).astype(np.float32)

    d0 = np.asarray(s.dof_pos, dtype=np.float32)
    d1 = np.asarray(t.dof_pos, dtype=np.float32)
    m0_dof = np.asarray(start_dof_vel, dtype=np.float32) * T * tension
    m1_dof = np.asarray(target_dof_vel, dtype=np.float32) * T * tension
    dof_pos = (
        h00[:, None] * d0[None, :]
        + h10[:, None] * m0_dof[None, :]
        + h01[:, None] * d1[None, :]
        + h11[:, None] * m1_dof[None, :]
    ).astype(np.float32)

    # Velocity-aware cubic reparameterization of SLERP
    q0 = _normalize_quat_xyzw(np.asarray(s.root_quat, dtype=np.float32))
    q1 = _normalize_quat_xyzw(np.asarray(t.root_quat, dtype=np.float32))
    dot = float(np.clip(np.dot(q0, q1), -1.0, 1.0))
    if dot < 0.0:
        q1 = -q1
        dot = -dot
    theta_total = float(np.arccos(np.clip(dot, -1.0, 1.0)))

    if theta_total > 1e-6 and start_ang_vel is not None and target_ang_vel is not None:
        omega_0 = float(np.linalg.norm(start_ang_vel))
        omega_1 = float(np.linalg.norm(target_ang_vel))
        d0_rot = omega_0 * T / theta_total
        d1_rot = omega_1 * T / theta_total
        m0_alpha = np.float32(d0_rot * tension)
        m1_alpha = np.float32(d1_rot * tension)
        rot_alpha = (
            h00 * 0.0
            + h10 * m0_alpha
            + h01 * alpha
            + h11 * m1_alpha
        )
        rot_alpha = np.clip(rot_alpha, 0.0, 1.0).astype(np.float32)
    else:
        rot_alpha = alpha

    root_rot = _slerp_xyzw(q0, q1, rot_alpha)

    local_body_pos = None
    if s.local_body_pos is not None and t.local_body_pos is not None:
        local_body_pos = (
            (1.0 - alpha[:, None, None]) * np.asarray(s.local_body_pos, dtype=np.float32)[None, :, :]
            + alpha[:, None, None] * np.asarray(t.local_body_pos, dtype=np.float32)[None, :, :]
        )
    elif t.local_body_pos is not None:
        local_body_pos = np.repeat(
            np.asarray(t.local_body_pos, dtype=np.float32)[None, :, :], num_frames, axis=0
        )

    return ReferenceFrames(
        fps=float(fps),
        root_pos=root_pos,
        root_rot=root_rot.astype(np.float32),
        dof_pos=dof_pos,
        local_body_pos=local_body_pos.astype(np.float32) if local_body_pos is not None else None,
    )


def compute_transition_metrics(
    transition_frames: ReferenceFrames,
    next_skill_frames: ReferenceFrames,
    interpolation_mode: str,
) -> TransitionMetrics:
    fps = float(transition_frames.fps)
    dt = 1.0 / fps
    pos = transition_frames.root_pos  # (N, 3)
    N = pos.shape[0]

    def _vel(p):
        v = np.zeros_like(p)
        if p.shape[0] < 2:
            return v
        v[0] = fps * (p[1] - p[0])
        v[-1] = fps * (p[-1] - p[-2])
        if p.shape[0] > 2:
            v[1:-1] = fps * (p[2:] - p[:-2]) / 2.0
        return v

    def _accel(p):
        a = np.zeros_like(p)
        if p.shape[0] < 3:
            return a
        a[1:-1] = (p[2:] - 2.0 * p[1:-1] + p[:-2]) / (dt ** 2)
        a[0] = a[1]
        a[-1] = a[-2]
        return a

    trans_vel = _vel(pos)
    trans_accel = _accel(pos)

    # Jerk from third finite difference (requires ≥5 frames)
    jerk_norms = np.zeros(N, dtype=np.float64)
    if N >= 5:
        for i in range(2, N - 2):
            j = (pos[i + 2] - 2.0 * pos[i + 1] + 2.0 * pos[i - 1] - pos[i - 2]) / (2.0 * dt ** 3)
            jerk_norms[i] = float(np.linalg.norm(j))
        valid = jerk_norms[2:N - 2]
        peak_jerk = float(np.max(valid)) if valid.size > 0 else 0.0
        mean_jerk = float(np.mean(valid)) if valid.size > 0 else 0.0
        auj = float(np.sum(valid) * dt)
    else:
        peak_jerk = 0.0
        mean_jerk = 0.0
        auj = 0.0

    # Seam metrics: compare end of transition to start of next skill
    n_next = next_skill_frames.root_pos.shape[0]
    if n_next >= 2:
        next_vel = _vel(next_skill_frames.root_pos)
        next_accel = _accel(next_skill_frames.root_pos)
        seam_vel_delta = float(np.linalg.norm(trans_vel[-1] - next_vel[0]))
        seam_accel_delta = float(np.linalg.norm(trans_accel[-1] - next_accel[1] if n_next > 2 else next_accel[0]))
    else:
        seam_vel_delta = 0.0
        seam_accel_delta = 0.0
        next_vel = np.zeros_like(next_skill_frames.root_pos)

    root_position_jump = float(
        np.linalg.norm(transition_frames.root_pos[-1, :2] - next_skill_frames.root_pos[0, :2])
    )
    root_height_jump = float(abs(transition_frames.root_pos[-1, 2] - next_skill_frames.root_pos[0, 2]))
    yaw0 = _yaw_from_xyzw(transition_frames.root_rot[-1])
    yaw1 = _yaw_from_xyzw(next_skill_frames.root_rot[0])
    yaw_jump = (yaw1 - yaw0 + np.pi) % (2.0 * np.pi) - np.pi
    root_yaw_jump_deg = float(abs(np.degrees(yaw_jump)))
    base_velocity_jump = seam_vel_delta
    dof_jump = np.abs(transition_frames.dof_pos[-1] - next_skill_frames.dof_pos[0])
    dof_position_jump_mean = float(np.mean(dof_jump))
    dof_position_jump_max = float(np.max(dof_jump))
    phase_penalty = (
        5.0 * root_position_jump
        + root_height_jump
        + abs(float(yaw_jump))
        + dof_position_jump_mean
        + 0.25 * base_velocity_jump
    )
    phase_compatibility_score = float(np.exp(-phase_penalty))

    return TransitionMetrics(
        seam_vel_delta=seam_vel_delta,
        seam_accel_delta=seam_accel_delta,
        peak_jerk=peak_jerk,
        mean_jerk=mean_jerk,
        auj=auj,
        interpolation_mode=interpolation_mode,
        num_frames=N,
        root_position_jump=root_position_jump,
        root_yaw_jump_deg=root_yaw_jump_deg,
        root_height_jump=root_height_jump,
        base_velocity_jump=base_velocity_jump,
        dof_position_jump_mean=dof_position_jump_mean,
        dof_position_jump_max=dof_position_jump_max,
        phase_compatibility_score=phase_compatibility_score,
    )


def reanchor_kinematic_frame(target_frame, current_state) -> KinematicFrame:
    """Align target_frame XY+yaw to current_state while preserving target Z and joint posture."""
    target = _as_kinematic_view(target_frame)
    current = _as_kinematic_view(current_state)
    current_pos = np.asarray(current.root_pos, dtype=np.float32)
    target_pos = np.asarray(target.root_pos, dtype=np.float32)
    new_pos = np.array([current_pos[0], current_pos[1], target_pos[2]], dtype=np.float32)
    current_yaw = _yaw_from_xyzw(np.asarray(current.root_quat, dtype=np.float32))
    target_yaw = _yaw_from_xyzw(np.asarray(target.root_quat, dtype=np.float32))
    delta_q = _yaw_quat_xyzw(current_yaw - target_yaw)
    new_quat = _quat_mul_xyzw(delta_q, np.asarray(target.root_quat, dtype=np.float32))
    return KinematicFrame(
        root_pos=new_pos,
        root_quat=new_quat,
        dof_pos=np.asarray(target.dof_pos, dtype=np.float32),
        local_body_pos=target.local_body_pos,
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
