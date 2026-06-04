import argparse
import os
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from low_level_execution.gmt_tracking_runner import GMTTrackingRunner
from middle_architecture.gmt_motion_adapter import load_gmt_motion
from middle_architecture.reference_ops import slice_motion_to_reference_frames


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


def _motion_path(motion: str) -> str:
    path = Path(motion)
    if path.exists():
        return str(path)
    local_motion = REPO_ROOT / "assets" / "motions" / motion
    if local_motion.exists():
        return str(local_motion)
    return str(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--motion", default="walk_stand.pkl")
    parser.add_argument("--duration", type=float, default=None)
    parser.add_argument("--gmt-root", default=_default_gmt_root())
    parser.add_argument("--robot", default="g1")
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()
    if not args.gmt_root:
        raise SystemExit("GMT root is required via --gmt-root, GMT_ROOT, or configs/harness.yaml")

    motion = load_gmt_motion(_motion_path(args.motion))
    end_frame = motion.num_frames
    if args.duration is not None:
        end_frame = min(motion.num_frames, max(2, int(round(args.duration * motion.fps))))
    reference_frames = slice_motion_to_reference_frames(motion, 0, end_frame)

    runner = GMTTrackingRunner(gmt_root=args.gmt_root, robot=args.robot, device=args.device)
    runner.initialize()
    result = runner.track(reference_frames)
    print(
        f"single motion result: success={result.success}, "
        f"frames={result.num_frames}, failed_reason={result.failed_reason}"
    )
    if not result.success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
