"""Run CHOREO C1-C6 validation commands in milestone order."""
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


COMMANDS = [
    ["scripts/validation/validate_skillmotion_schema.py"],
    [
        "scripts/convert_qpos_clips_to_skillmotion.py",
        "--skills",
        "configs/skills.yaml",
        "--output",
        "skillmotion_library",
    ],
    ["scripts/validation/validate_qpos_clip_adapter.py"],
    [
        "scripts/convert_qpos_clips_to_skillmotion.py",
        "--skills",
        "configs/skills.yaml",
        "--output",
        "skillmotion_library",
    ],
    ["scripts/validation/validate_skillmotion_features.py"],
    ["scripts/validation/validate_tracker_adapter_parity.py"],
    ["scripts/validation/validate_skillmotion_pipeline_parity.py"],
    ["scripts/validation/validate_execution_monitor.py"],
]


for command in COMMANDS:
    full = [sys.executable] + [str(REPO_ROOT / command[0])] + command[1:]
    print("\n$ " + " ".join(command))
    subprocess.check_call(full, cwd=str(REPO_ROOT))

print("\nCHOREO C1-C6 validation suite passed.")
