"""Single-window MuJoCo viewer playback for a generated HumaSkill sequence."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from humaskill.composer.rule_based_composer import RuleBasedDanceComposer
from humaskill.harness.sequence_validator import SequenceValidator
from humaskill.harness.transition_manager import TransitionManager
from humaskill.skills.skill_registry import SkillRegistry


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "model" / "g1_description" / "g1_23dof.xml"
SKILLS_PATH = PROJECT_ROOT / "configs" / "skills.yaml"
CLIP_MAP = {
    "stand_ready": PROJECT_ROOT / "motions" / "stand_ready_qpos.npy",
    "arm_wave": PROJECT_ROOT / "motions" / "arm_wave_qpos.npy",
    "final_pose": PROJECT_ROOT / "motions" / "final_pose_qpos.npy",
}


def rel(path: Path) -> str:
    """Return a stable project-relative path string."""
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Generate a HumaSkill sequence and play available qpos clips in one MuJoCo viewer.",
    )
    parser.add_argument("--text", required=True, help="Natural language instruction.")
    parser.add_argument("--duration", required=True, type=float, help="Target sequence duration in seconds.")
    parser.add_argument("--seed", default=42, type=int, help="Composer seed.")
    parser.add_argument("--fps", default=30.0, type=float, help="Viewer playback FPS.")
    parser.add_argument("--loop", action="store_true", help="Loop the full played sequence until viewer closes.")
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Maximum frames to play per clip.",
    )
    parser.add_argument(
        "--output-sequence",
        default=None,
        help="Optional JSON path for generated, played, and skipped sequence details.",
    )
    return parser.parse_args()


def generate_sequence(text: str, duration: float, seed: int = 42) -> list[dict]:
    """Generate and repair a HumaSkill sequence using existing composer logic."""
    registry = SkillRegistry(str(SKILLS_PATH))
    composer = RuleBasedDanceComposer(registry)
    raw_sequence = composer.compose(text, duration, seed)
    SequenceValidator(registry).validate(raw_sequence)
    return TransitionManager(registry).repair(raw_sequence)


def build_play_plan(sequence: list[dict]) -> tuple[list[dict], list[dict]]:
    """Map sequence skills to available qpos clips and collect skipped skills."""
    played: list[dict] = []
    skipped: list[dict] = []
    for item in sequence:
        skill = item["skill"]
        clip_path = CLIP_MAP.get(skill)
        if clip_path is None or not clip_path.exists():
            print(f"[WARN] Missing qpos clip for skill: {skill}")
            skipped.append({**item, "reason": "missing_qpos_clip"})
            continue
        played.append({**item, "clip": rel(clip_path)})
    return played, skipped


def save_sequence_report(
    output_path: Path,
    text: str,
    duration: float,
    generated_sequence: list[dict],
    played_sequence: list[dict],
    skipped_skills: list[dict],
) -> None:
    """Save generated and played sequence details to JSON."""
    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "text": text,
        "duration": duration,
        "generated_sequence": generated_sequence,
        "played_sequence": played_sequence,
        "skipped_skills": skipped_skills,
    }
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[INFO] Sequence report saved to: {output_path}")


def validate_motion(motion: np.ndarray, model: Any, clip_path: Path) -> None:
    """Validate clip shape against model qpos dimension."""
    if motion.ndim != 2:
        raise ValueError(f"{rel(clip_path)} must be 2D, got shape {motion.shape}")
    if motion.shape[1] != model.nq:
        raise ValueError(f"{rel(clip_path)} qpos dim {motion.shape[1]} does not match model.nq {model.nq}")


def play_sequence(
    mujoco: Any,
    model: Any,
    data: Any,
    played_sequence: list[dict],
    fps: float,
    loop: bool,
    max_frames: int | None,
) -> None:
    """Play all qpos clips in one MuJoCo viewer window."""
    import mujoco.viewer

    frame_period = 1.0 / fps
    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            for item in played_sequence:
                clip_path = PROJECT_ROOT / item["clip"]
                motion = np.load(clip_path)
                validate_motion(motion, model, clip_path)
                frame_count = motion.shape[0]
                if max_frames is not None:
                    frame_count = min(frame_count, max_frames)
                for frame in motion[:frame_count]:
                    if not viewer.is_running():
                        break
                    start = time.perf_counter()
                    data.qpos[:] = frame
                    mujoco.mj_forward(model, data)
                    viewer.sync()
                    elapsed = time.perf_counter() - start
                    if elapsed < frame_period:
                        time.sleep(frame_period - elapsed)
                if not viewer.is_running():
                    break
            if not loop:
                break


def main() -> int:
    """Run single-viewer HumaSkill sequence playback."""
    args = parse_args()
    if args.fps <= 0:
        raise ValueError(f"--fps must be positive, got {args.fps}")
    if args.max_frames is not None and args.max_frames <= 0:
        raise ValueError(f"--max-frames must be positive, got {args.max_frames}")

    generated_sequence = generate_sequence(args.text, args.duration, args.seed)
    played_sequence, skipped_skills = build_play_plan(generated_sequence)

    print("Generated sequence:")
    for item in generated_sequence:
        print(f"  - {item['skill']} ({item['duration']}s, source={item.get('source', 'agent')})")
    print("Played sequence:")
    for item in played_sequence:
        print(f"  - {item['skill']} -> {item['clip']}")

    if args.output_sequence:
        save_sequence_report(
            Path(args.output_sequence),
            args.text,
            args.duration,
            generated_sequence,
            played_sequence,
            skipped_skills,
        )

    if not played_sequence:
        print("[WARN] No playable qpos clips found; viewer will not open.")
        return 0

    try:
        import mujoco
    except ImportError:
        print("MuJoCo is not installed. Install with: python -m pip install mujoco")
        return 0

    model = mujoco.MjModel.from_xml_path(str(MODEL_PATH))
    data = mujoco.MjData(model)
    try:
        play_sequence(mujoco, model, data, played_sequence, args.fps, args.loop, args.max_frames)
    except KeyboardInterrupt:
        print("[INFO] Playback interrupted by user.")

    print("Final played skill list:")
    print(", ".join(item["skill"] for item in played_sequence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
