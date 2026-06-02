"""Tests for local G1 retargeted motion inspection/conversion data."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "g1-retargeted-motions"
METADATA_PATH = PROJECT_ROOT / "motions" / "metadata.json"


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a project-local command and capture text output."""
    return subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )


def test_g1_data_dir_and_pickles_exist() -> None:
    """The downloaded retargeted G1 data is present locally."""
    assert DATA_DIR.exists()
    assert any(DATA_DIR.rglob("*.pkl"))


def test_convert_g1_pkl_to_npy_generates_metadata_and_2d_clips() -> None:
    """The converter writes metadata and 2D .npy clips."""
    run_command([sys.executable, "scripts/convert_g1_pkl_to_npy.py"])

    assert METADATA_PATH.exists()
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    motions = metadata.get("motions", [])
    assert len(motions) >= 1

    for item in motions:
        output_file = item["output_file"]
        clip_path = PROJECT_ROOT / output_file
        assert clip_path.exists(), output_file
        clip = np.load(clip_path)
        assert clip.ndim == 2
        assert clip.shape[0] > 0
        assert clip.shape[1] > 0
