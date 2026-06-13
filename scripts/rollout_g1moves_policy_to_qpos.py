#!/usr/bin/env python3
"""Roll out a pretrained g1-moves ONNX policy in MuJoCo and save qpos.

This script intentionally copies the small amount of control logic needed from
external/g1-moves-code/run_policy.py so it can run independently inside
HumaSkill. It performs inference only; it does not train or update any policy.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import sys
import time

import mujoco
import numpy as np
import onnxruntime as ort


DEFAULT_JOINT_POS = np.zeros(29, dtype=np.float32)

# g1-moves policy/control rates: 50 Hz control, 200 Hz MuJoCo simulation.
DECIMATION = 4
CONTROL_DT = 0.02

# PD gains copied from external/g1-moves-code/run_policy.py.
KP = np.array(
    [
        40.2,
        99.1,
        40.2,
        99.1,
        28.6,
        28.6,
        40.2,
        99.1,
        40.2,
        99.1,
        28.6,
        28.6,
        40.2,
        28.6,
        28.6,
        14.3,
        14.3,
        14.3,
        14.3,
        14.3,
        16.8,
        16.8,
        14.3,
        14.3,
        14.3,
        14.3,
        14.3,
        16.8,
        16.8,
    ],
    dtype=np.float32,
)

KD = np.array(
    [
        2.6,
        6.3,
        2.6,
        6.3,
        1.8,
        1.8,
        2.6,
        6.3,
        2.6,
        6.3,
        1.8,
        1.8,
        2.6,
        1.8,
        1.8,
        0.9,
        0.9,
        0.9,
        0.9,
        0.9,
        1.1,
        1.1,
        0.9,
        0.9,
        0.9,
        0.9,
        0.9,
        1.1,
        1.1,
    ],
    dtype=np.float32,
)


def rotation_matrix_to_6d(rot_matrix: np.ndarray) -> np.ndarray:
    """Extract the first two columns of a 3x3 rotation matrix."""
    return rot_matrix[:, :2].T.flatten()


def quat_to_rot_matrix(quat_wxyz: np.ndarray) -> np.ndarray:
    """Convert a wxyz quaternion to a 3x3 rotation matrix."""
    w, x, y, z = quat_wxyz
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )


def transform_to_body_frame(
    pos_world: np.ndarray,
    quat_world_wxyz: np.ndarray,
    anchor_pos_world: np.ndarray,
    anchor_quat_world_wxyz: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Transform reference anchor position/orientation into robot body frame."""
    robot_rot = quat_to_rot_matrix(quat_world_wxyz)
    anchor_rot = quat_to_rot_matrix(anchor_quat_world_wxyz)

    anchor_pos_body = robot_rot.T @ (anchor_pos_world - pos_world)
    anchor_ori_body = rotation_matrix_to_6d(robot_rot.T @ anchor_rot)

    return anchor_pos_body.astype(np.float32), anchor_ori_body.astype(np.float32)


def resolve_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{label} file not found: {path}")


def load_motion(npz_path: Path) -> dict[str, np.ndarray | float]:
    required_keys = [
        "fps",
        "joint_pos",
        "joint_vel",
        "body_pos_w",
        "body_quat_w",
    ]
    with np.load(npz_path) as motion:
        missing = [key for key in required_keys if key not in motion]
        if missing:
            raise KeyError(f"NPZ missing required key(s): {', '.join(missing)}")

        fps = float(np.asarray(motion["fps"]).reshape(-1)[0])
        joint_pos = np.asarray(motion["joint_pos"], dtype=np.float32)
        joint_vel = np.asarray(motion["joint_vel"], dtype=np.float32)
        body_pos_w = np.asarray(motion["body_pos_w"], dtype=np.float32)
        body_quat_w = np.asarray(motion["body_quat_w"], dtype=np.float32)

    if not math.isfinite(fps) or fps <= 0.0:
        raise ValueError(f"Invalid fps in NPZ: {fps}")
    if joint_pos.ndim != 2 or joint_pos.shape[1] != 29:
        raise ValueError(f"Expected joint_pos shape [T, 29], got {joint_pos.shape}")
    if joint_vel.shape != joint_pos.shape:
        raise ValueError(f"Expected joint_vel shape {joint_pos.shape}, got {joint_vel.shape}")
    if body_pos_w.ndim != 3 or body_pos_w.shape[0] != joint_pos.shape[0] or body_pos_w.shape[2] != 3:
        raise ValueError(f"Expected body_pos_w shape [T, N, 3], got {body_pos_w.shape}")
    if body_quat_w.ndim != 3 or body_quat_w.shape[:2] != body_pos_w.shape[:2] or body_quat_w.shape[2] != 4:
        raise ValueError(f"Expected body_quat_w shape [T, N, 4], got {body_quat_w.shape}")

    return {
        "fps": fps,
        "joint_pos": joint_pos,
        "joint_vel": joint_vel,
        "body_pos_w": body_pos_w,
        "body_quat_w": body_quat_w,
    }


def load_policy(onnx_path: Path) -> tuple[ort.InferenceSession, str, str]:
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])

    input_names = [inp.name for inp in session.get_inputs()]
    output_names = [out.name for out in session.get_outputs()]
    if "obs" not in input_names:
        raise ValueError(f"ONNX input 'obs' not found. Available inputs: {input_names}")
    if "actions" not in output_names:
        raise ValueError(f"ONNX output 'actions' not found. Available outputs: {output_names}")

    obs_meta = session.get_inputs()[input_names.index("obs")]
    act_meta = session.get_outputs()[output_names.index("actions")]
    if len(obs_meta.shape) != 2 or obs_meta.shape[1] != 160:
        raise ValueError(f"Expected ONNX obs shape [batch, 160], got {obs_meta.shape}")
    if len(act_meta.shape) != 2 or act_meta.shape[1] != 29:
        raise ValueError(f"Expected ONNX actions shape [batch, 29], got {act_meta.shape}")

    return session, "obs", "actions"


def validate_model(model: mujoco.MjModel) -> None:
    expected = {"nq": 36, "nv": 35, "nu": 29}
    actual = {"nq": model.nq, "nv": model.nv, "nu": model.nu}
    if actual != expected:
        raise ValueError(f"Expected MuJoCo model dimensions {expected}, got {actual}")


def actuator_force_limits(model: mujoco.MjModel) -> tuple[np.ndarray, np.ndarray] | None:
    """Return per-actuator joint force limits from the XML when available."""
    if model.actuator_trnid.shape[0] != model.nu:
        return None

    joint_ids = model.actuator_trnid[:, 0].astype(np.int32)
    if np.any(joint_ids < 0):
        return None

    ranges = model.jnt_actfrcrange[joint_ids].astype(np.float32)
    lows = ranges[:, 0]
    highs = ranges[:, 1]
    if not np.all(np.isfinite(ranges)) or not np.all(lows < highs):
        return None
    return lows, highs


def actuator_joint_position_limits(model: mujoco.MjModel) -> tuple[np.ndarray, np.ndarray] | None:
    """Return per-actuator joint position limits from the XML when available."""
    if model.actuator_trnid.shape[0] != model.nu:
        return None

    joint_ids = model.actuator_trnid[:, 0].astype(np.int32)
    if np.any(joint_ids < 0):
        return None

    limited = model.jnt_limited[joint_ids].astype(bool)
    if not np.all(limited):
        return None

    ranges = model.jnt_range[joint_ids].astype(np.float32)
    lows = ranges[:, 0]
    highs = ranges[:, 1]
    if not np.all(np.isfinite(ranges)) or not np.all(lows < highs):
        return None
    return lows, highs


def rollout(
    onnx_path: Path,
    npz_path: Path,
    xml_path: Path,
    output_path: Path,
    seconds: float,
    speed: float,
    use_viewer: bool,
) -> np.ndarray:
    if seconds <= 0.0 or not math.isfinite(seconds):
        raise ValueError(f"--seconds must be a positive finite number, got {seconds}")
    if speed <= 0.0 or not math.isfinite(speed):
        raise ValueError(f"--speed must be a positive finite number, got {speed}")

    motion = load_motion(npz_path)
    ref_joint_pos = motion["joint_pos"]
    ref_joint_vel = motion["joint_vel"]
    ref_body_pos = motion["body_pos_w"]
    ref_body_quat = motion["body_quat_w"]
    fps = float(motion["fps"])
    num_frames = ref_joint_pos.shape[0]
    duration = num_frames / fps

    session, input_name, output_name = load_policy(onnx_path)

    model = mujoco.MjModel.from_xml_path(str(xml_path))
    validate_model(model)
    model.opt.timestep = CONTROL_DT / DECIMATION
    if hasattr(mujoco.mjtIntegrator, "mjINT_IMPLICITFAST"):
        model.opt.integrator = mujoco.mjtIntegrator.mjINT_IMPLICITFAST
    elif hasattr(mujoco.mjtIntegrator, "mjINT_IMPLICIT"):
        model.opt.integrator = mujoco.mjtIntegrator.mjINT_IMPLICIT
    data = mujoco.MjData(model)
    torque_limits = actuator_force_limits(model)
    joint_position_limits = actuator_joint_position_limits(model)

    data.qpos[:3] = ref_body_pos[0, 0]
    data.qpos[3:7] = ref_body_quat[0, 0]
    data.qpos[7:36] = ref_joint_pos[0]
    mujoco.mj_forward(model, data)

    control_steps = int(math.ceil(seconds / CONTROL_DT))
    qpos_log = np.empty((control_steps, model.nq), dtype=np.float64)

    print(f"motion frames: {num_frames}, fps: {fps:g}, reference duration: {duration:.3f}s")
    print(f"control steps: {control_steps}, sim timestep: {model.opt.timestep:g}s")
    print(f"integrator: {model.opt.integrator}")
    print(f"joint target limits: {'from XML joint ranges' if joint_position_limits is not None else 'none'}")
    print(f"torque limits: {'from XML joint actuatorfrcrange' if torque_limits is not None else 'none'}")
    print(f"viewer: {'on' if use_viewer else 'off'}")

    last_action = np.zeros(29, dtype=np.float32)
    motion_time = 0.0

    def motion_frame(t: float) -> int:
        return int(t * fps) % num_frames

    def control_once() -> None:
        nonlocal last_action, motion_time

        frame = motion_frame(motion_time)

        ref_jp = ref_joint_pos[frame].astype(np.float32)
        ref_jv = ref_joint_vel[frame].astype(np.float32)

        robot_pos = data.qpos[:3].copy()
        robot_quat_wxyz = data.qpos[3:7].copy()
        joint_pos = data.qpos[7:36].astype(np.float32)
        joint_vel = data.qvel[6:35].astype(np.float32)

        if data.sensordata.size >= 6:
            base_ang_vel = data.sensordata[:3].astype(np.float32)
            base_lin_vel = data.sensordata[3:6].astype(np.float32)
        else:
            base_ang_vel = np.zeros(3, dtype=np.float32)
            base_lin_vel = np.zeros(3, dtype=np.float32)

        anchor_pos_w = ref_body_pos[frame, 0].astype(np.float64)
        anchor_quat_w = ref_body_quat[frame, 0].astype(np.float64)
        anchor_pos_b, anchor_ori_b = transform_to_body_frame(
            robot_pos, robot_quat_wxyz, anchor_pos_w, anchor_quat_w
        )

        obs = np.concatenate(
            [
                ref_jp,
                ref_jv,
                anchor_pos_b,
                anchor_ori_b,
                base_ang_vel,
                base_lin_vel,
                joint_pos - DEFAULT_JOINT_POS,
                joint_vel,
                last_action,
            ]
        ).astype(np.float32)
        if obs.shape != (160,):
            raise RuntimeError(f"Internal observation shape error: expected (160,), got {obs.shape}")

        actions = session.run([output_name], {input_name: obs[None, :]})[0][0].astype(np.float32)
        if actions.shape != (29,):
            raise RuntimeError(f"ONNX action shape error: expected (29,), got {actions.shape}")
        if not np.isfinite(actions).all():
            raise RuntimeError(f"ONNX policy returned non-finite action at frame {frame}: {actions}")

        last_action = actions.copy()
        target_pos = actions + DEFAULT_JOINT_POS
        if joint_position_limits is not None:
            joint_lows, joint_highs = joint_position_limits
            target_pos = np.clip(target_pos, joint_lows, joint_highs)
        torques = KP * (target_pos - joint_pos) - KD * joint_vel
        if torque_limits is not None:
            torque_lows, torque_highs = torque_limits
            torques = np.clip(torques, torque_lows, torque_highs)
        data.ctrl[:29] = torques

        motion_time += CONTROL_DT * speed

    def run_steps(viewer=None) -> None:
        for step in range(control_steps):
            step_start = time.time()

            control_once()
            for _ in range(DECIMATION):
                mujoco.mj_step(model, data)

            qpos_log[step] = data.qpos.copy()

            if not np.isfinite(qpos_log[step]).all():
                raise RuntimeError(f"Non-finite qpos produced at control step {step}")

            if viewer is not None:
                viewer.sync()
                elapsed = time.time() - step_start
                sleep_time = CONTROL_DT - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

    if use_viewer:
        from mujoco import viewer as mujoco_viewer

        with mujoco_viewer.launch_passive(model, data) as viewer:
            run_steps(viewer)
    else:
        run_steps()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(output_path, qpos_log)
    return qpos_log


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Roll out a pretrained g1-moves ONNX policy in MuJoCo and save qpos npy."
    )
    parser.add_argument("--onnx", required=True, help="Path to g1-moves ONNX policy.")
    parser.add_argument("--npz", required=True, help="Path to paired g1-moves NPZ reference file.")
    parser.add_argument("--xml", required=True, help="Path to G1 29-DoF MuJoCo XML.")
    parser.add_argument("--output", required=True, help="Output .npy path for qpos, shape [T, 36].")
    parser.add_argument("--seconds", type=float, required=True, help="Rollout duration in seconds.")
    parser.add_argument("--speed", type=float, default=1.0, help="Reference playback speed multiplier.")
    viewer_group = parser.add_mutually_exclusive_group()
    viewer_group.add_argument("--viewer", action="store_true", help="Launch a MuJoCo viewer.")
    viewer_group.add_argument("--no-viewer", action="store_true", help="Run headless. This is the default.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        onnx_path = resolve_path(args.onnx)
        npz_path = resolve_path(args.npz)
        xml_path = resolve_path(args.xml)
        output_path = resolve_path(args.output)

        require_file(onnx_path, "ONNX")
        require_file(npz_path, "NPZ")
        require_file(xml_path, "XML")

        use_viewer = bool(args.viewer and not args.no_viewer)
        qpos = rollout(
            onnx_path=onnx_path,
            npz_path=npz_path,
            xml_path=xml_path,
            output_path=output_path,
            seconds=args.seconds,
            speed=args.speed,
            use_viewer=use_viewer,
        )

        print(f"saved path: {output_path}")
        print(f"qpos shape: {qpos.shape}")
        print(f"has NaN: {np.isnan(qpos).any()}")
        with np.printoptions(precision=6, suppress=True):
            print(f"first qpos: {qpos[0]}")
            print(f"last qpos: {qpos[-1]}")
        return 0

    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
