from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
import math
import os
from pathlib import Path
from typing import Optional

import numpy as np
import torch

from middle_architecture.evaluation import (
    EvaluationBuffer,
    SegmentMetrics,
    compute_first_second_stability,
    compute_segment_metrics,
)
from middle_architecture.robot_state import ReferenceFrames, RobotState


@dataclass
class RunnerTrackResult:
    success: bool
    num_frames: int
    log_path: Optional[str] = None
    video_path: Optional[str] = None
    failed_reason: Optional[str] = None
    metrics: Optional[SegmentMetrics] = None
    diagnostics: Optional[dict] = None


@dataclass
class FallConfig:
    enabled: bool = True
    min_root_height: float = 0.20
    max_body_tilt: float = 120.0


@contextmanager
def _working_directory(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _quat_wxyz_to_euler(quat: np.ndarray) -> np.ndarray:
    qw, qx, qy, qz = quat
    euler = np.zeros(3, dtype=np.float32)
    sinr_cosp = 2.0 * (qw * qx + qy * qz)
    cosr_cosp = 1.0 - 2.0 * (qx * qx + qy * qy)
    euler[0] = math.atan2(sinr_cosp, cosr_cosp)

    sinp = 2.0 * (qw * qy - qz * qx)
    if abs(sinp) >= 1.0:
        euler[1] = math.copysign(math.pi / 2.0, sinp)
    else:
        euler[1] = math.asin(sinp)

    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    euler[2] = math.atan2(siny_cosp, cosy_cosp)
    return euler


def _quat_xyzw_to_euler_batch(quat: np.ndarray):
    x = quat[:, 0]
    y = quat[:, 1]
    z = quat[:, 2]
    w = quat[:, 3]
    roll = np.arctan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y))
    pitch_arg = np.clip(2.0 * (w * y - z * x), -1.0, 1.0)
    pitch = np.arcsin(pitch_arg)
    yaw = np.arctan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
    return roll.astype(np.float32), pitch.astype(np.float32), yaw.astype(np.float32)


def _quat_rotate_inverse_xyzw(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    q_w = q[:, 3:4]
    q_vec = q[:, :3]
    a = v * (2.0 * q_w * q_w - 1.0)
    b = np.cross(q_vec, v) * q_w * 2.0
    c = q_vec * np.sum(q_vec * v, axis=1, keepdims=True) * 2.0
    return (a - b + c).astype(np.float32)


def _quat_conjugate_xyzw(q: np.ndarray) -> np.ndarray:
    out = q.copy()
    out[..., :3] *= -1.0
    return out


def _quat_mul_xyzw(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    x1, y1, z1, w1 = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    x2, y2, z2, w2 = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
    ww = (z1 + x1) * (x2 + y2)
    yy = (w1 - y1) * (w2 + z2)
    zz = (w1 + y1) * (w2 - z2)
    xx = ww + yy + zz
    qq = 0.5 * (xx + (z1 - x1) * (x2 - y2))
    w = qq - ww + (z1 - y1) * (y2 - z2)
    x = qq - xx + (x1 + w1) * (x2 + w2)
    y = qq - yy + (w1 - x1) * (y2 + z2)
    z = qq - zz + (z1 + y1) * (w2 - x2)
    return np.stack([x, y, z, w], axis=-1).astype(np.float32)


def _quat_to_exp_map_xyzw(q: np.ndarray) -> np.ndarray:
    q = q / np.clip(np.linalg.norm(q, axis=-1, keepdims=True), 1e-9, None)
    sin_theta = np.sqrt(np.clip(1.0 - q[..., 3] * q[..., 3], 0.0, None))
    angle = 2.0 * np.arccos(np.clip(q[..., 3], -1.0, 1.0))
    angle = np.arctan2(np.sin(angle), np.cos(angle))
    axis = np.zeros_like(q[..., :3])
    mask = np.abs(sin_theta) > 1e-5
    axis[mask] = q[..., :3][mask] / sin_theta[mask, None]
    axis[~mask, 2] = 1.0
    angle = np.where(mask, angle, 0.0)
    return (axis * angle[..., None]).astype(np.float32)


def _slerp_xyzw(q0: np.ndarray, q1: np.ndarray, blend: np.ndarray) -> np.ndarray:
    q0 = q0 / np.clip(np.linalg.norm(q0, axis=-1, keepdims=True), 1e-9, None)
    q1 = q1 / np.clip(np.linalg.norm(q1, axis=-1, keepdims=True), 1e-9, None)
    cos_half_theta = np.sum(q0 * q1, axis=-1)
    neg_mask = cos_half_theta < 0.0
    q1 = np.where(neg_mask[:, None], -q1, q1)
    cos_half_theta = np.abs(cos_half_theta)
    cos_half_theta = np.clip(cos_half_theta, -1.0, 1.0)
    half_theta = np.arccos(cos_half_theta)
    sin_half_theta = np.sqrt(np.clip(1.0 - cos_half_theta * cos_half_theta, 0.0, None))
    blend = blend.astype(np.float32)

    ratio_a = np.empty_like(blend)
    ratio_b = np.empty_like(blend)
    linear_mask = sin_half_theta < 0.001
    ratio_a[linear_mask] = 1.0 - blend[linear_mask]
    ratio_b[linear_mask] = blend[linear_mask]
    ratio_a[~linear_mask] = (
        np.sin((1.0 - blend[~linear_mask]) * half_theta[~linear_mask])
        / sin_half_theta[~linear_mask]
    )
    ratio_b[~linear_mask] = (
        np.sin(blend[~linear_mask] * half_theta[~linear_mask])
        / sin_half_theta[~linear_mask]
    )
    out = ratio_a[:, None] * q0 + ratio_b[:, None] * q1
    out = out / np.clip(np.linalg.norm(out, axis=-1, keepdims=True), 1e-9, None)
    return out.astype(np.float32)


def _smooth_same(x: np.ndarray, box_pts: int) -> np.ndarray:
    if x.shape[0] == 0:
        return x
    kernel = np.ones(box_pts, dtype=np.float32) / float(box_pts)
    pad = box_pts // 2
    padded = np.pad(x, ((pad, pad), (0, 0)), mode="constant")
    cols = [np.convolve(padded[:, i], kernel, mode="valid") for i in range(x.shape[1])]
    return np.stack(cols, axis=1).astype(np.float32)


def _estimate_body_tilt_degrees(root_quat_wxyz: np.ndarray) -> float:
    q = np.asarray(root_quat_wxyz, dtype=np.float64)
    q = q / max(np.linalg.norm(q), 1e-9)
    qw, qx, qy, qz = q
    up_z = 1.0 - 2.0 * (qx * qx + qy * qy)
    up_z = float(np.clip(up_z, -1.0, 1.0))
    return math.degrees(math.acos(up_z))


def _env_flag(name: str) -> bool:
    value = os.environ.get(name, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


class _ReferenceSampler:
    def __init__(self, reference_frames: ReferenceFrames):
        self.fps = float(reference_frames.fps)
        self.root_pos = np.asarray(reference_frames.root_pos, dtype=np.float32)
        self.root_rot = np.asarray(reference_frames.root_rot, dtype=np.float32)
        self.dof_pos = np.asarray(reference_frames.dof_pos, dtype=np.float32)
        if self.root_pos.shape[0] < 2:
            raise ValueError("reference_frames must contain at least two frames")
        self.num_frames = int(self.root_pos.shape[0])
        self.length = (self.num_frames - 1) / self.fps
        self.root_vel, self.root_ang_vel, self.dof_vel = self._derive_velocities()

    def _derive_velocities(self):
        root_vel = np.zeros_like(self.root_pos)
        root_vel[:-1, :] = self.fps * (self.root_pos[1:, :] - self.root_pos[:-1, :])
        root_vel[-1, :] = root_vel[-2, :]
        root_vel = _smooth_same(root_vel, 19)

        root_ang_vel = np.zeros_like(self.root_pos)
        drot = _quat_mul_xyzw(self.root_rot[1:], _quat_conjugate_xyzw(self.root_rot[:-1]))
        root_ang_vel[:-1, :] = self.fps * _quat_to_exp_map_xyzw(drot)
        root_ang_vel[-1, :] = root_ang_vel[-2, :]
        root_ang_vel = _smooth_same(root_ang_vel, 19)

        dof_vel = np.zeros_like(self.dof_pos)
        dof_vel[:-1, :] = self.fps * (self.dof_pos[1:, :] - self.dof_pos[:-1, :])
        dof_vel[-1, :] = dof_vel[-2, :]
        dof_vel = _smooth_same(dof_vel, 19)
        return root_vel, root_ang_vel, dof_vel

    def sample(self, times: np.ndarray):
        times = np.asarray(times, dtype=np.float32)
        if self.length <= 0.0:
            wrapped = np.zeros_like(times)
        else:
            wrapped = times - np.floor(times / self.length) * self.length
        phase = np.clip(wrapped / self.length, 0.0, 1.0)
        frame_idx0 = (phase * (self.num_frames - 1)).astype(np.int64)
        frame_idx1 = np.minimum(frame_idx0 + 1, self.num_frames - 1)
        blend = phase * (self.num_frames - 1) - frame_idx0.astype(np.float32)

        root_pos = (
            (1.0 - blend[:, None]) * self.root_pos[frame_idx0]
            + blend[:, None] * self.root_pos[frame_idx1]
        )
        root_rot = _slerp_xyzw(self.root_rot[frame_idx0], self.root_rot[frame_idx1], blend)
        dof_pos = (
            (1.0 - blend[:, None]) * self.dof_pos[frame_idx0]
            + blend[:, None] * self.dof_pos[frame_idx1]
        )
        return (
            root_pos.astype(np.float32),
            root_rot.astype(np.float32),
            self.root_vel[frame_idx0].astype(np.float32),
            self.root_ang_vel[frame_idx0].astype(np.float32),
            dof_pos.astype(np.float32),
            self.dof_vel[frame_idx0].astype(np.float32),
        )


class GMTTrackingRunner:
    def __init__(
        self,
        gmt_root,
        robot,
        device="auto",
        fall_config=None,
        render=None,
        model_path=None,
        policy_path=None,
    ):
        self.gmt_root = Path(gmt_root)
        self.robot = robot
        self.model_path = Path(model_path) if model_path is not None else None
        self.policy_path = Path(policy_path) if policy_path is not None else None
        self.device = device
        self.torch_device = None
        self.fall_config = self._coerce_fall_config(fall_config)
        self.render = _env_flag("HUMASKILL_RENDER") if render is None else bool(render)

        self.model = None
        self.data = None
        self.policy_jit = None
        self.split_viewer = None
        self.initialized = False
        self._foot_body_ids = None

        self.sim_duration = 60.0
        self.sim_dt = 0.001
        self.sim_decimation = 20
        self.control_dt = self.sim_dt * self.sim_decimation

        self.num_actions = 23
        self.num_dofs = 23
        self.default_dof_pos = np.array(
            [
                -0.2,
                0.0,
                0.0,
                0.4,
                -0.2,
                0.0,
                -0.2,
                0.0,
                0.0,
                0.4,
                -0.2,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.4,
                0.0,
                1.2,
                0.0,
                -0.4,
                0.0,
                1.2,
            ],
            dtype=np.float32,
        )
        self.stiffness = np.array(
            [
                100,
                100,
                100,
                150,
                40,
                40,
                100,
                100,
                100,
                150,
                40,
                40,
                150,
                150,
                150,
                40,
                40,
                40,
                40,
                40,
                40,
                40,
                40,
            ],
            dtype=np.float32,
        )
        self.damping = np.array(
            [
                2,
                2,
                2,
                4,
                2,
                2,
                2,
                2,
                2,
                4,
                2,
                2,
                4,
                4,
                4,
                5,
                5,
                5,
                5,
                5,
                5,
                5,
                5,
            ],
            dtype=np.float32,
        )
        self.torque_limits = np.array(
            [
                88,
                139,
                88,
                139,
                50,
                50,
                88,
                139,
                88,
                139,
                50,
                50,
                88,
                50,
                50,
                25,
                25,
                25,
                25,
                25,
                25,
                25,
                25,
            ],
            dtype=np.float32,
        )

        self.action_scale = 0.5
        self.tar_obs_steps = np.array(
            [1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95],
            dtype=np.int32,
        )
        self.n_proprio = 3 + 2 + 3 * self.num_actions
        self.history_len = 20
        self.dof_pos_scale = 1.0
        self.dof_vel_scale = 0.05
        self.ang_vel_scale = 0.25
        self.last_action = np.zeros(self.num_actions, dtype=np.float32)
        self.pd_target = self.default_dof_pos.copy()
        self.proprio_history_buf = deque(maxlen=self.history_len)

    def _coerce_fall_config(self, fall_config):
        if fall_config is None:
            return FallConfig()
        if isinstance(fall_config, FallConfig):
            return fall_config
        return FallConfig(
            enabled=bool(fall_config.get("enabled", True)),
            min_root_height=float(fall_config.get("min_root_height", 0.20)),
            max_body_tilt=float(fall_config.get("max_body_tilt", 120.0)),
        )

    def _resolve_device(self):
        if self.device == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        if self.device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("device='cuda' requested but CUDA is not available")
        return self.device

    def _resolve_model_path(self) -> Path:
        if self.model_path is None:
            return self.gmt_root / "assets" / "robots" / self.robot / f"{self.robot}.xml"
        if self.model_path.is_absolute():
            return self.model_path
        return (Path.cwd() / self.model_path).resolve()

    def _resolve_policy_path(self) -> Path:
        if self.policy_path is None:
            return self.gmt_root / "assets" / "pretrained_checkpoints" / "pretrained.pt"
        if self.policy_path.is_absolute():
            return self.policy_path
        return (Path.cwd() / self.policy_path).resolve()

    def initialize(self):
        if self.initialized:
            return
        if self.robot != "g1":
            raise ValueError(f"Robot type {self.robot} not supported")
        if not self.gmt_root.exists():
            raise FileNotFoundError(f"GMT root not found: {self.gmt_root}")

        import mujoco

        self.torch_device = self._resolve_device()
        model_path = self._resolve_model_path()
        policy_path = self._resolve_policy_path()
        if not model_path.exists():
            raise FileNotFoundError(f"MuJoCo model not found: {model_path}")
        if not policy_path.exists():
            raise FileNotFoundError(f"Policy checkpoint not found: {policy_path}")

        with _working_directory(model_path.parent):
            self.model = mujoco.MjModel.from_xml_path(str(model_path))
        self.model.opt.timestep = self.sim_dt
        self.data = mujoco.MjData(self.model)
        mujoco.mj_resetDataKeyframe(self.model, self.data, 0)
        mujoco.mj_step(self.model, self.data)

        self.policy_jit = torch.jit.load(str(policy_path), map_location=self.torch_device)
        self.policy_jit.eval()
        if self.render:
            from low_level_execution.split_viewer import SplitScreenViewer

            self.split_viewer = SplitScreenViewer(self.model, self.data, num_dofs=self.num_dofs)
        self.last_action = np.zeros(self.num_actions, dtype=np.float32)
        self.pd_target = self.default_dof_pos.copy()
        self.proprio_history_buf.clear()
        for _ in range(self.history_len):
            self.proprio_history_buf.append(np.zeros(self.n_proprio, dtype=np.float32))
        self.initialized = True

    def get_robot_state(self) -> RobotState:
        self._require_initialized()
        qpos = self.data.qpos.astype(np.float32)
        qvel = self.data.qvel.astype(np.float32)
        return RobotState(
            root_pos=qpos[:3].copy(),
            root_quat=qpos[3:7].copy(),
            dof_pos=qpos[-self.num_dofs :].copy(),
            root_lin_vel=qvel[:3].copy(),
            root_ang_vel=qvel[3:6].copy(),
            dof_vel=qvel[-self.num_dofs :].copy(),
        )

    def reset_to_reference_frame(self, reference_frames: ReferenceFrames) -> None:
        self._require_initialized()
        if reference_frames.root_pos.shape[0] < 1:
            raise ValueError("reference_frames must contain at least one frame")

        import mujoco

        root_rot_xyzw = np.asarray(reference_frames.root_rot[0], dtype=np.float32)
        root_quat_wxyz = np.array(
            [root_rot_xyzw[3], root_rot_xyzw[0], root_rot_xyzw[1], root_rot_xyzw[2]],
            dtype=np.float32,
        )
        self.data.qpos[:3] = np.asarray(reference_frames.root_pos[0], dtype=np.float32)
        self.data.qpos[3:7] = root_quat_wxyz
        self.data.qpos[-self.num_dofs :] = np.asarray(reference_frames.dof_pos[0], dtype=np.float32)
        self.data.qvel[:] = 0.0
        self.last_action = np.zeros(self.num_actions, dtype=np.float32)
        self.pd_target = np.asarray(reference_frames.dof_pos[0], dtype=np.float32).copy()
        mujoco.mj_forward(self.model, self.data)
        self._fill_proprio_history_from_current_state()

    def _sample_reference_at_step(
        self, sampler: "_ReferenceSampler", control_step: int
    ):
        t = np.array([control_step * self.control_dt], dtype=np.float32)
        root_pos, root_rot, root_vel, _, dof_pos, _ = sampler.sample(t)
        return root_pos[0], root_rot[0], dof_pos[0], root_vel[0]

    def track(
        self,
        reference_frames: ReferenceFrames,
        future_reference_frames: ReferenceFrames = None,
        control_mode: str = "policy",
        action_ramp_steps: int = 0,
        segment_label: Optional[str] = None,
    ) -> RunnerTrackResult:
        self._require_initialized()
        if self.split_viewer is not None:
            self.split_viewer.set_label(segment_label)
        if control_mode not in {"policy", "pd_hold"}:
            raise ValueError(f"Unsupported control_mode: {control_mode}")
        sampler = _ReferenceSampler(reference_frames)
        future_sampler = (
            _ReferenceSampler(future_reference_frames)
            if future_reference_frames is not None
            else None
        )
        num_control_steps = max(1, int(math.ceil(sampler.length / self.control_dt)))
        _buffer = EvaluationBuffer()

        for control_step in range(num_control_steps):
            ref_rp, ref_rr, ref_dof, ref_vel = self._sample_reference_at_step(sampler, control_step)
            previous_action = self.last_action.copy()

            if control_mode == "pd_hold":
                self.last_action = np.zeros(self.num_actions, dtype=np.float32)
                self.pd_target = ref_dof.astype(np.float32).copy()
            else:
                obs = self._build_observation(sampler, control_step, future_sampler=future_sampler)
                obs_tensor = torch.from_numpy(obs).float().unsqueeze(0).to(self.torch_device)
                with torch.no_grad():
                    raw_action = self.policy_jit(obs_tensor).detach().cpu().numpy().squeeze()
                raw_action = np.clip(raw_action, -10.0, 10.0)
                if action_ramp_steps > 0 and control_step < action_ramp_steps:
                    alpha = float(control_step + 1) / float(action_ramp_steps)
                    raw_action = (1.0 - alpha) * previous_action + alpha * raw_action
                self.last_action = raw_action.astype(np.float32).copy()
                scaled_actions = raw_action * self.action_scale
                self.pd_target = scaled_actions.astype(np.float32) + self.default_dof_pos

            for _ in range(self.sim_decimation):
                self._step_mujoco_physics()

            self._render_frame(ref_rp, ref_rr, ref_dof)

            state = self.get_robot_state()
            runtime_diag = self._capture_runtime_diagnostics(state)
            _buffer.record(
                step=control_step,
                tracked_root_pos=state.root_pos,
                tracked_root_quat_wxyz=state.root_quat,
                tracked_dof_pos=state.dof_pos,
                tracked_lin_vel=state.root_lin_vel,
                ref_root_pos=ref_rp,
                ref_root_rot_xyzw=ref_rr,
                ref_dof_pos=ref_dof,
                ref_lin_vel=ref_vel,
                base_roll=runtime_diag["base_roll"],
                base_pitch=runtime_diag["base_pitch"],
                qvel_norm=runtime_diag["qvel_norm"],
                root_velocity_norm=runtime_diag["root_velocity_norm"],
                foot_contacts=runtime_diag["foot_contacts"],
                foot_positions=runtime_diag["foot_positions"],
            )
            if control_mode == "pd_hold":
                self.proprio_history_buf.append(self._compute_proprio_obs())

            if self._has_fallen():
                metrics = compute_segment_metrics(
                    _buffer, self.control_dt, self.fall_config.min_root_height,
                    reference_fps=sampler.fps,
                )
                diagnostics = {
                    "first_second_stability": compute_first_second_stability(
                        _buffer, self.control_dt
                    )
                }
                return RunnerTrackResult(
                    success=False,
                    num_frames=control_step + 1,
                    failed_reason="fell",
                    metrics=metrics,
                    diagnostics=diagnostics,
                )

        metrics = compute_segment_metrics(
            _buffer, self.control_dt, self.fall_config.min_root_height,
            reference_fps=sampler.fps,
        )
        diagnostics = {
            "first_second_stability": compute_first_second_stability(
                _buffer, self.control_dt
            )
        }
        return RunnerTrackResult(
            success=True,
            num_frames=num_control_steps,
            metrics=metrics,
            diagnostics=diagnostics,
        )

    def _require_initialized(self):
        if not self.initialized:
            raise RuntimeError("GMTTrackingRunner is not initialized. Call initialize() first.")

    def _extract_data(self):
        dof_pos = self.data.qpos.astype(np.float32)[-self.num_dofs :]
        dof_vel = self.data.qvel.astype(np.float32)[-self.num_dofs :]
        quat = self.data.sensor("orientation").data.astype(np.float32)
        ang_vel = self.data.sensor("angular-velocity").data.astype(np.float32)
        return dof_pos.copy(), dof_vel.copy(), quat.copy(), ang_vel.copy()

    def _compute_proprio_obs(self) -> np.ndarray:
        dof_pos, dof_vel, quat, ang_vel = self._extract_data()
        rpy = _quat_wxyz_to_euler(quat)
        obs_dof_vel = dof_vel.copy()
        obs_dof_vel[[4, 5, 10, 11]] = 0.0
        obs_prop = np.concatenate(
            [
                ang_vel * self.ang_vel_scale,
                rpy[:2],
                (dof_pos - self.default_dof_pos) * self.dof_pos_scale,
                obs_dof_vel * self.dof_vel_scale,
                self.last_action,
            ]
        ).astype(np.float32)
        if obs_prop.shape[0] != self.n_proprio:
            raise RuntimeError(f"Expected proprio dim {self.n_proprio}, got {obs_prop.shape[0]}")
        return obs_prop

    def _fill_proprio_history_from_current_state(self) -> None:
        obs_prop = self._compute_proprio_obs()
        self.proprio_history_buf.clear()
        for _ in range(self.history_len):
            self.proprio_history_buf.append(obs_prop.copy())

    def _get_foot_body_ids(self):
        if self._foot_body_ids is not None:
            return self._foot_body_ids
        ids = {}
        for foot, body_name in {
            "left": "left_ankle_roll_link",
            "right": "right_ankle_roll_link",
        }.items():
            try:
                ids[foot] = int(self.model.body(body_name).id)
            except Exception:
                ids[foot] = None
        self._foot_body_ids = ids
        return ids

    def _get_foot_contacts(self):
        foot_ids = self._get_foot_body_ids()
        contacts = {foot: False for foot in foot_ids}
        if not contacts:
            return contacts
        for i in range(int(self.data.ncon)):
            contact = self.data.contact[i]
            body1 = int(self.model.geom_bodyid[int(contact.geom1)])
            body2 = int(self.model.geom_bodyid[int(contact.geom2)])
            for foot, body_id in foot_ids.items():
                if body_id is not None and (body1 == body_id or body2 == body_id):
                    contacts[foot] = True
        return contacts

    def _get_foot_positions(self):
        positions = {}
        for foot, body_id in self._get_foot_body_ids().items():
            if body_id is None:
                continue
            positions[foot] = self.data.xpos[body_id].astype(np.float32).copy()
        return positions

    def _capture_runtime_diagnostics(self, state: RobotState):
        rpy = _quat_wxyz_to_euler(state.root_quat)
        qvel = self.data.qvel.astype(np.float32)
        root_velocity_norm = float(np.linalg.norm(state.root_lin_vel))
        return {
            "base_roll": float(rpy[0]),
            "base_pitch": float(rpy[1]),
            "qvel_norm": float(np.linalg.norm(qvel)),
            "root_velocity_norm": root_velocity_norm,
            "foot_contacts": self._get_foot_contacts(),
            "foot_positions": self._get_foot_positions(),
        }

    def _build_observation(
        self,
        sampler: _ReferenceSampler,
        control_step: int,
        future_sampler: _ReferenceSampler = None,
    ) -> np.ndarray:
        mimic_obs = self._get_mimic_obs(
            sampler,
            control_step,
            future_sampler=future_sampler,
        )
        obs_prop = self._compute_proprio_obs()
        obs_hist = np.array(self.proprio_history_buf, dtype=np.float32).flatten()
        obs_buf = np.concatenate([mimic_obs, obs_prop, obs_hist]).astype(np.float32)
        self.proprio_history_buf.append(obs_prop)
        return obs_buf

    def _sample_future_reference_window(
        self,
        sampler: _ReferenceSampler,
        motion_times: np.ndarray,
        future_sampler: _ReferenceSampler = None,
    ):
        root_pos, root_rot, root_vel, root_ang_vel, dof_pos, dof_vel = sampler.sample(motion_times)
        if future_sampler is None:
            return root_pos, root_rot, root_vel, root_ang_vel, dof_pos, dof_vel

        future_mask = motion_times >= sampler.length
        if not np.any(future_mask):
            return root_pos, root_rot, root_vel, root_ang_vel, dof_pos, dof_vel

        future_times = motion_times[future_mask] - sampler.length
        (
            future_root_pos,
            future_root_rot,
            future_root_vel,
            future_root_ang_vel,
            future_dof_pos,
            future_dof_vel,
        ) = future_sampler.sample(future_times)
        root_pos[future_mask] = future_root_pos
        root_rot[future_mask] = future_root_rot
        root_vel[future_mask] = future_root_vel
        root_ang_vel[future_mask] = future_root_ang_vel
        dof_pos[future_mask] = future_dof_pos
        dof_vel[future_mask] = future_dof_vel
        return root_pos, root_rot, root_vel, root_ang_vel, dof_pos, dof_vel

    def _get_mimic_obs(
        self,
        sampler: _ReferenceSampler,
        control_step: int,
        future_sampler: _ReferenceSampler = None,
    ) -> np.ndarray:
        motion_time = control_step * self.control_dt
        obs_motion_times = self.tar_obs_steps.astype(np.float32) * self.control_dt + motion_time
        root_pos, root_rot, root_vel, root_ang_vel, dof_pos, _ = (
            self._sample_future_reference_window(
                sampler,
                obs_motion_times,
                future_sampler=future_sampler,
            )
        )
        roll, pitch, _ = _quat_xyzw_to_euler_batch(root_rot)
        root_vel = _quat_rotate_inverse_xyzw(root_rot, root_vel)
        root_ang_vel = _quat_rotate_inverse_xyzw(root_rot, root_ang_vel)
        mimic_obs = np.concatenate(
            [
                root_pos[:, 2:3],
                roll[:, None],
                pitch[:, None],
                root_vel,
                root_ang_vel[:, 2:3],
                dof_pos,
            ],
            axis=-1,
        )
        return mimic_obs.reshape(-1).astype(np.float32)

    def _step_mujoco_physics(self):
        import mujoco

        dof_pos = self.data.qpos.astype(np.float32)[-self.num_dofs :]
        dof_vel = self.data.qvel.astype(np.float32)[-self.num_dofs :]
        torque = (self.pd_target - dof_pos) * self.stiffness - dof_vel * self.damping
        torque = np.clip(torque, -self.torque_limits, self.torque_limits)
        self.data.ctrl[:] = torque
        mujoco.mj_step(self.model, self.data)

    def _render_frame(self, ref_rp=None, ref_rr=None, ref_dof=None):
        if self.split_viewer is None:
            return
        if ref_rp is not None:
            self.split_viewer.update_reference(ref_rp, ref_rr, ref_dof)
        self.split_viewer.render()

    def _has_fallen(self) -> bool:
        if not self.fall_config.enabled:
            return False
        state = self.get_robot_state()
        root_height = float(state.root_pos[2])
        body_tilt = _estimate_body_tilt_degrees(state.root_quat)
        if root_height < self.fall_config.min_root_height:
            return True
        if body_tilt > self.fall_config.max_body_tilt:
            return True
        return False
