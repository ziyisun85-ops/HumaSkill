#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
import yaml


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Skill name, e.g. dad_dance_reference")
    parser.add_argument("--input", required=True, help="Input qpos30 npy path")
    parser.add_argument("--fps", type=float, required=True)
    parser.add_argument("--start-frame", type=int, default=0)
    parser.add_argument("--end-frame", type=int, default=None)
    parser.add_argument("--copy", action="store_true")
    parser.add_argument("--create-demo-sequence", action="store_true")
    parser.add_argument("--add-transitions", action="store_true")
    return parser.parse_args()


def validate_qpos30(path: Path) -> np.ndarray:
    qpos = np.load(path)

    if qpos.ndim != 2:
        raise ValueError(f"Expected 2D array, got shape {qpos.shape}")

    if qpos.shape[1] != 30:
        raise ValueError(f"Expected qpos30 shape [T, 30], got {qpos.shape}")

    if np.isnan(qpos).any():
        raise ValueError("qpos contains NaN")

    quat_norm = np.linalg.norm(qpos[:, 3:7], axis=1)

    print("input:", path)
    print("shape:", qpos.shape)
    print("root xyz min:", qpos[:, :3].min(axis=0))
    print("root xyz max:", qpos[:, :3].max(axis=0))
    print("quat norm min/max:", quat_norm.min(), quat_norm.max())
    print("joint min/max:", qpos[:, 7:].min(), qpos[:, 7:].max())

    return qpos


def update_skills(skill_name: str, motion_file: str, fps: float, start: int, end: int | None):
    path = Path("configs/skills.yaml")
    data = yaml.safe_load(path.read_text())

    skills = data.setdefault("skills", {})

    skills[skill_name] = {
        "motion_file": motion_file,
        "default_start_frame": start,
        "default_end_frame": end,
        "fps": float(fps),
        "description": f"Imported qpos30 trajectory skill: {skill_name}.",
    }

    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    print("updated:", path)


def create_demo_sequence(skill_name: str):
    path = Path(f"configs/sequences/demo_{skill_name}.yaml")
    path.parent.mkdir(parents=True, exist_ok=True)

    text = f"""task_id: demo_{skill_name}

sequence:
  - skill: stable_stand_bridge
    duration: 2.0

  - skill: {skill_name}

  - skill: stable_stand_bridge
    duration: 2.0
"""
    path.write_text(text)
    print("created:", path)


def add_transitions(skill_name: str):
    path = Path("configs/transitions.yaml")
    data = yaml.safe_load(path.read_text())

    transitions = data.setdefault("transitions", [])

    def exists(a: str, b: str) -> bool:
        return any(
            t.get("from_skill") == a and t.get("to_skill") == b
            for t in transitions
        )

    new_items = [
        {
            "from_skill": "stable_stand_bridge",
            "to_skill": skill_name,
            "mode": "interpolation",
            "num_frames": 24,
            "interpolation_mode": "hermite",
            "hermite_tension": 0.1,
            "reason": f"stable_stand_to_{skill_name}_uses_short_hermite_interpolation",
        },
        {
            "from_skill": skill_name,
            "to_skill": "stable_stand_bridge",
            "mode": "interpolation",
            "num_frames": 24,
            "interpolation_mode": "hermite",
            "hermite_tension": 0.1,
            "reason": f"{skill_name}_to_stable_stand_uses_short_hermite_interpolation",
        },
    ]

    added = 0
    for item in new_items:
        if not exists(item["from_skill"], item["to_skill"]):
            transitions.append(item)
            added += 1

    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    print(f"updated: {path}, added {added} transitions")


def main():
    args = parse_args()

    input_path = Path(args.input)
    qpos = validate_qpos30(input_path)

    if args.end_frame is None:
        end_frame = qpos.shape[0]
    else:
        end_frame = args.end_frame

    if args.copy:
        dst = Path("assets/motions/g1_23dof") / f"{args.name}.npy"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(input_path, dst)
        motion_file = str(dst)
        print("copied to:", dst)
    else:
        motion_file = str(input_path)

    update_skills(
        skill_name=args.name,
        motion_file=motion_file,
        fps=args.fps,
        start=args.start_frame,
        end=end_frame,
    )

    if args.create_demo_sequence:
        create_demo_sequence(args.name)

    if args.add_transitions:
        add_transitions(args.name)

    print("DONE")


if __name__ == "__main__":
    main()
