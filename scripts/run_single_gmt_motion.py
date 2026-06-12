import argparse
import json
import os
from pathlib import Path
import sys

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from low_level_execution.gmt_tracking_runner import GMTTrackingRunner
from middle_architecture.gmt_motion_adapter import GmtMotionAdapter, get_kinematic_frame
from middle_architecture.gmt_motion_adapter import load_gmt_motion
from middle_architecture.reference_ops import (
    concat_reference_frames,
    interpolate_reference_frames,
    reanchor_kinematic_frame,
    slice_motion_to_reference_frames,
)
from task_plan.skill_registry import SkillRegistry


def _default_gmt_root():
    env_root = os.environ.get("GMT_ROOT")
    if env_root:
        return env_root
    config_path = REPO_ROOT / "configs" / "harness.yaml"
    if not config_path.exists():
        return None
    in_gmt = False
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "gmt:":
            in_gmt = True
            continue
        if raw_line and not raw_line.startswith(" ") and not raw_line.startswith("\t"):
            in_gmt = False
        if in_gmt and line.startswith("root:"):
            return line.split(":", 1)[1].strip().strip("\"'")
    return None


def _load_harness_config(path: str = "configs/harness.yaml") -> dict:
    config_path = REPO_ROOT / path
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _motion_path(motion: str) -> str:
    path = Path(motion)
    if path.exists():
        return str(path)
    local_motion = REPO_ROOT / "assets" / "motions" / motion
    if local_motion.exists():
        return str(local_motion)
    return str(path)


def build_initial_stabilization_frames(
    state,
    stabilization_config,
    skill_registry,
    motion_adapter,
):
    if not bool(stabilization_config.get("enabled", False)):
        return None, {"reset_to_stand_ready": False, "action_ramp_steps": 0}

    stand_skill_name = stabilization_config.get("stand_ready_skill", "stable_stand_bridge")
    blend_frames = int(stabilization_config.get("blend_frames", 20))
    hold_frames = int(stabilization_config.get("hold_frames", 40))
    total_frames = blend_frames + hold_frames
    if total_frames <= 0:
        return None, {"reset_to_stand_ready": False, "action_ramp_steps": 0}

    stand_skill = skill_registry.get(stand_skill_name)
    stand_motion = motion_adapter.load(stand_skill.motion_file)
    stand_idx = int(stand_skill.default_start_frame)
    stand_frame = get_kinematic_frame(stand_motion, stand_idx)
    anchored_stand = reanchor_kinematic_frame(stand_frame, state)
    if bool(stabilization_config.get("preserve_initial_root_height", True)):
        anchored_stand.root_pos = anchored_stand.root_pos.copy()
        anchored_stand.root_pos[2] = state.root_pos[2]

    reset_to_stand_ready = bool(stabilization_config.get("reset_to_stand_ready", False))
    parts = []
    if reset_to_stand_ready:
        parts.append(
            interpolate_reference_frames(
                anchored_stand,
                anchored_stand,
                num_frames=total_frames,
                fps=stand_motion.fps,
            )
        )
    else:
        if blend_frames > 0:
            parts.append(
                interpolate_reference_frames(
                    state,
                    anchored_stand,
                    num_frames=blend_frames,
                    fps=stand_motion.fps,
                )
            )
        if hold_frames > 0:
            parts.append(
                interpolate_reference_frames(
                    anchored_stand,
                    anchored_stand,
                    num_frames=hold_frames,
                    fps=stand_motion.fps,
                )
            )

    return concat_reference_frames(parts), {
        "reset_to_stand_ready": reset_to_stand_ready,
        "action_ramp_steps": int(stabilization_config.get("action_ramp_frames", 0)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--motion", default="walk_stand.pkl")
    parser.add_argument("--duration", type=float, default=None)
    parser.add_argument("--gmt-root", default=_default_gmt_root())
    parser.add_argument("--robot", default="g1")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--config", default="configs/harness.yaml")
    parser.add_argument("--no-stabilization", action="store_true")
    parser.add_argument(
        "--render",
        action="store_true",
        help="show the live split-screen viewer (reference | tracker); "
        "also enabled by setting HUMASKILL_RENDER=1",
    )
    args = parser.parse_args()
    if not args.gmt_root:
        raise SystemExit("GMT root is required via --gmt-root, GMT_ROOT, or configs/harness.yaml")

    config = _load_harness_config(args.config)
    motion = load_gmt_motion(_motion_path(args.motion))
    end_frame = motion.num_frames
    if args.duration is not None:
        end_frame = min(motion.num_frames, max(2, int(round(args.duration * motion.fps))))
    reference_frames = slice_motion_to_reference_frames(motion, 0, end_frame)

    runner = GMTTrackingRunner(
        gmt_root=args.gmt_root,
        robot=args.robot,
        device=args.device,
        model_path=(config.get("gmt") or {}).get("model_path"),
        policy_path=(config.get("gmt") or {}).get("policy_path"),
        fall_config=config.get("fall_detection"),
        render=True if args.render else None,
    )
    runner.initialize()
    if not args.no_stabilization:
        stabilization_config = config.get("initial_stabilization", {})
        motion_adapter = GmtMotionAdapter((config.get("motion_assets") or {}).get("root", "assets/motions"))
        skill_registry = SkillRegistry.from_yaml("configs/skills.yaml")
        stabilization_frames, stabilization_runtime = build_initial_stabilization_frames(
            state=runner.get_robot_state(),
            stabilization_config=stabilization_config,
            skill_registry=skill_registry,
            motion_adapter=motion_adapter,
        )
        if stabilization_frames is not None:
            if stabilization_runtime["reset_to_stand_ready"]:
                runner.reset_to_reference_frame(stabilization_frames)
            stabilization_result = runner.track(
                stabilization_frames,
                action_ramp_steps=stabilization_runtime["action_ramp_steps"],
                segment_label="stabilization_stand_ready",
            )
            print(
                f"single stabilization result: success={stabilization_result.success}, "
                f"frames={stabilization_result.num_frames}, "
                f"failed_reason={stabilization_result.failed_reason}"
            )
            if stabilization_result.diagnostics:
                print(
                    "single stabilization first_second="
                    + json.dumps(stabilization_result.diagnostics.get("first_second_stability", {}))
                )
            if not stabilization_result.success:
                raise SystemExit(1)

    result = runner.track(reference_frames, segment_label=Path(args.motion).name)
    print(
        f"single motion result: success={result.success}, "
        f"frames={result.num_frames}, failed_reason={result.failed_reason}"
    )
    if not result.success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
