"""Non-viewer tests for the single-window HumaSkill MuJoCo sequence script."""

from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "view_humaskill_sequence_in_mujoco.py"


def load_script_module():
    """Load the viewer script without executing main."""
    spec = importlib.util.spec_from_file_location("view_humaskill_sequence_in_mujoco", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_script_imports_successfully() -> None:
    """The script can be imported without opening a viewer."""
    module = load_script_module()
    assert module.MODEL_PATH.exists()


def test_clip_mapping_finds_existing_clips() -> None:
    """Known playable skills map to existing qpos clips."""
    module = load_script_module()
    for skill in ["stand_ready", "arm_wave", "final_pose"]:
        assert module.CLIP_MAP[skill].exists()


def test_generated_dance_sequence_includes_arm_wave() -> None:
    """Dance shorthand should generate an arm_wave clip for the visual demo."""
    module = load_script_module()
    sequence = module.generate_sequence("跳一段舞", 8.0, seed=42)
    assert "arm_wave" in [item["skill"] for item in sequence]


def test_missing_clips_are_skipped_without_crashing() -> None:
    """Unmapped skills are skipped and reported by build_play_plan."""
    module = load_script_module()
    sequence = [
        {"skill": "stand_ready", "duration": 1.0, "source": "agent"},
        {"skill": "body_sway", "duration": 1.0, "source": "agent"},
        {"skill": "final_pose", "duration": 1.0, "source": "agent"},
    ]
    played, skipped = module.build_play_plan(sequence)
    assert [item["skill"] for item in played] == ["stand_ready", "final_pose"]
    assert [item["skill"] for item in skipped] == ["body_sway"]
