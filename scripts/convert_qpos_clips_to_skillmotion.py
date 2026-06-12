import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from middle_architecture.source_adapters.qpos_clip import convert_registry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skills", default="configs/skills.yaml")
    parser.add_argument("--output", default="skillmotion_library")
    parser.add_argument(
        "--motions-root",
        default=".",
        help="Root used to resolve relative motion paths from the skill registry.",
    )
    args = parser.parse_args()

    converted = convert_registry(
        skills_yaml=args.skills,
        output_root=args.output,
        motions_root=args.motions_root,
    )
    for name, motion in sorted(converted.items()):
        print(
            f"{name}: frames={motion.num_frames} fps={motion.fps:.6f} "
            f"qpos={tuple(motion.qpos.shape)} qvel={tuple(motion.qvel.shape)}"
        )


if __name__ == "__main__":
    main()
