"""Kinematic playback of a GMT motion pkl in a render window (no physics, no policy)."""
import argparse
from pathlib import Path
import sys
import time

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from middle_architecture.gmt_motion_adapter import load_gmt_motion


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--motion", required=True, help="motion pkl name or path")
    parser.add_argument("--model", default="assets/robots/g1/g1.xml")
    parser.add_argument("--loops", type=int, default=2)
    parser.add_argument("--speed", type=float, default=1.0, help="playback speed multiplier")
    args = parser.parse_args()

    import cv2
    import mujoco

    motion_path = Path(args.motion)
    if not motion_path.exists():
        motion_path = REPO_ROOT / "assets" / "motions" / args.motion
    motion = load_gmt_motion(str(motion_path))
    num_dofs = motion.dof_pos.shape[1]
    print(f"{motion_path.name}: {motion.num_frames} frames @ {motion.fps:.1f} fps "
          f"({motion.num_frames / motion.fps:.1f}s)")

    model_path = (REPO_ROOT / args.model).resolve()
    model = mujoco.MjModel.from_xml_path(str(model_path))
    data = mujoco.MjData(model)
    renderer = mujoco.Renderer(model, 480, 640)
    cam = mujoco.MjvCamera()
    cam.distance = 3.5
    cam.elevation = -15
    cam.azimuth = 90

    frame_dt = 1.0 / (motion.fps * args.speed)
    font = cv2.FONT_HERSHEY_SIMPLEX
    for loop in range(args.loops):
        for idx in range(motion.num_frames):
            t0 = time.perf_counter()
            x, y, z, w = motion.root_rot[idx]
            data.qpos[:3] = motion.root_pos[idx]
            data.qpos[3:7] = [w, x, y, z]  # MuJoCo expects wxyz
            data.qpos[7:7 + num_dofs] = motion.dof_pos[idx]
            mujoco.mj_kinematics(model, data)

            cam.lookat[:] = data.qpos[:3]
            renderer.update_scene(data, cam)
            img = renderer.render().copy()
            img = cv2.resize(img, (960, 720), interpolation=cv2.INTER_LINEAR)
            cv2.putText(img, motion_path.name, (10, 30), font, 0.9, (0, 255, 255), 2)
            cv2.putText(img, f"loop {loop + 1}/{args.loops}  frame {idx + 1}/{motion.num_frames}",
                        (10, 60), font, 0.7, (255, 255, 255), 2)
            cv2.imshow("HumaSkill Clip Player", img[:, :, ::-1])
            if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                print("playback aborted by user")
                return
            remaining = frame_dt - (time.perf_counter() - t0)
            if remaining > 0:
                time.sleep(remaining)

    cv2.destroyAllWindows()
    renderer.close()


if __name__ == "__main__":
    main()
