#!/usr/bin/env python3
"""Run the HumaSkill demo with default parameters.

Equivalent to:
    python -m humaskill.main --text "跳一段 12 秒的欢快机器人舞蹈" \
        --duration 12 --seed 42 --fail-prob 0.1 --backend dummy \
        --output logs/demo_log.json

Usage:
    python scripts/run_demo.py
"""

import sys
from pathlib import Path

# Resolve the project root (parent of the scripts directory).
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent

# Add project root to sys.path so humaskill is importable.
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Change working directory to project root so relative paths
# (e.g. logs/demo_log.json) resolve correctly.
import os
os.chdir(str(project_root))

from humaskill.main import main

if __name__ == "__main__":
    demo_args = [
        "--text", "跳一段 12 秒的欢快机器人舞蹈",
        "--duration", "12",
        "--seed", "42",
        "--fail-prob", "0.1",
        "--backend", "dummy",
        "--output", "logs/demo_log.json",
    ]
    sys.exit(main(demo_args))
