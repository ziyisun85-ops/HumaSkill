"""Validate CHOREO SkillMotion feature extraction artifacts."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np

from middle_architecture.skill_motion import load_skillmotion
from task_plan.skill_registry import SkillRegistry


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS = REPO_ROOT / "configs" / "skills.yaml"
LIBRARY = REPO_ROOT / "skillmotion_library"


if not LIBRARY.exists():
    subprocess.check_call(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "convert_qpos_clips_to_skillmotion.py"),
            "--skills",
            str(SKILLS),
            "--output",
            str(LIBRARY),
        ],
        cwd=str(REPO_ROOT),
    )


registry = SkillRegistry.from_yaml(str(SKILLS))
required = {
    "qvel",
    "root_linear_velocity_world",
    "root_linear_velocity_heading",
    "root_angular_velocity",
    "heading",
    "left_foot_contact",
    "right_foot_contact",
    "foot_contact_confidence",
    "entry_window",
    "exit_window",
}

for skill_name in sorted(registry.skills.keys()):
    motion = load_skillmotion(str(LIBRARY), skill_name)
    missing = required - set(motion.features.keys())
    assert not missing, (skill_name, missing)
    n = motion.num_frames
    assert np.array_equal(motion.features["qvel"], motion.qvel), skill_name
    for key in [
        "root_linear_velocity_world",
        "root_linear_velocity_heading",
        "root_angular_velocity",
    ]:
        assert motion.features[key].shape == (n, 3), (skill_name, key, motion.features[key].shape)
        assert np.all(np.isfinite(motion.features[key])), (skill_name, key)
    assert motion.features["heading"].shape == (n,), skill_name
    heading_step = np.diff(motion.features["heading"])
    if heading_step.size:
        assert float(np.max(np.abs(heading_step))) < np.pi, skill_name
    for key in ["left_foot_contact", "right_foot_contact"]:
        values = motion.features[key]
        assert values.shape == (n,), (skill_name, key)
        assert np.all((values == 0.0) | (values == 1.0)), (skill_name, key)
    assert motion.features["foot_contact_confidence"].shape == (n, 2), skill_name
    entry = motion.features["entry_window"]
    exit_ = motion.features["exit_window"]
    assert entry.shape == (2,) and exit_.shape == (2,), skill_name
    assert motion.boundaries.entry_window_start == int(entry[0])
    assert motion.boundaries.entry_window_end == int(entry[1])
    assert motion.boundaries.exit_window_start == int(exit_[0])
    assert motion.boundaries.exit_window_end == int(exit_[1])
    print(
        f"{skill_name}: features OK; entry={entry.tolist()} "
        f"exit={exit_.tolist()} "
        f"entry_low={motion.boundaries.entry_window_low_confidence} "
        f"exit_low={motion.boundaries.exit_window_low_confidence}"
    )

walk = load_skillmotion(str(LIBRARY), "walk_forward")
left = walk.features["left_foot_contact"].astype(bool)
right = walk.features["right_foot_contact"].astype(bool)
left_only = float(np.mean(left & ~right))
right_only = float(np.mean(right & ~left))
both = float(np.mean(left & right))
assert left_only > 0.20, left_only
assert right_only > 0.20, right_only
assert both < 0.25, both
print(
    "walk_forward foot contacts: "
    f"left_only={left_only:.3f} right_only={right_only:.3f} both={both:.3f}"
)

stand = load_skillmotion(str(LIBRARY), "stable_stand_bridge")
stand_left = stand.features["left_foot_contact"].astype(bool)
stand_right = stand.features["right_foot_contact"].astype(bool)
first_both = float(np.mean(stand_left[:10] & stand_right[:10]))
last_both = float(np.mean(stand_left[-10:] & stand_right[-10:]))
assert first_both >= 0.80, first_both
assert last_both >= 0.80, last_both
assert not stand.boundaries.entry_window_low_confidence
assert not stand.boundaries.exit_window_low_confidence
print(
    "stable_stand_bridge double contact and stable boundary windows OK: "
    f"first10={first_both:.3f} last10={last_both:.3f}"
)

print("SkillMotion feature validation passed.")
