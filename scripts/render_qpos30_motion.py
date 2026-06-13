#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
from pathlib import Path

# Headless server rendering. Must be set before importing mujoco.
os.environ.setdefault("MUJOCO_GL", "egl")

import imageio.v2 as imageio
import mujoco
import numpy as np


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--xml", required=True, help="MuJoCo XML path")
    parser.add_argument("--motion", required=True, help="qpos30 npy path")
    parser.add_argument("--output", required=True, help="output mp4 path")
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    return parser.parse_args()


def main():
    args = parse_args()

    xml_path = Path(args.xml)
    motion_path = Path(args.motion)
    output_path = Path(args.output)

    if not xml_path.is_file():
        raise FileNotFoundError(f"XML not found: {xml_path}")

    if not motion_path.is_file():
        raise FileNotFoundError(f"Motion not found: {motion_path}")

    qpos = np.load(motion_path)

    if qpos.ndim != 2:
        raise ValueError(f"Expected 2D qpos array, got {qpos.shape}")

    if qpos.shape[1] != 30:
        raise ValueError(f"Expected qpos30 shape [T, 30], got {qpos.shape}")

    if np.isnan(qpos).any():
        raise ValueError("qpos contains NaN")

    model = mujoco.MjModel.from_xml_path(str(xml_path))
    data = mujoco.MjData(model)

    print("xml:", xml_path)
    print("motion:", motion_path)
    print("qpos shape:", qpos.shape)
    print("model nq:", model.nq)
    print("model nv:", model.nv)
    print("model nu:", model.nu)

    if model.nq != qpos.shape[1]:
        raise ValueError(f"Model nq={model.nq}, but qpos dim={qpos.shape[1]}")

    num_frames = qpos.shape[0]
    if args.max_frames is not None:
        num_frames = min(num_frames, args.max_frames)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Camera setup.
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.azimuth = 135
    cam.elevation = -15
    cam.distance = 3.0
    cam.lookat[:] = np.array([0.0, 0.0, 0.8])

    renderer = mujoco.Renderer(model, height=args.height, width=args.width)

    print("rendering frames:", num_frames)
    print("output:", output_path)

    with imageio.get_writer(str(output_path), fps=args.fps, codec="libx264", quality=8) as writer:
        for i in range(num_frames):
            data.qpos[:] = qpos[i]
            data.qvel[:] = 0.0
            mujoco.mj_forward(model, data)

            renderer.update_scene(data, camera=cam)
            frame = renderer.render()
            writer.append_data(frame)

            if i % 50 == 0:
                print(f"frame {i}/{num_frames}")

    renderer.close()
    print("DONE")


if __name__ == "__main__":
    main()
