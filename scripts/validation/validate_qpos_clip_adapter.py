"""Validate qpos clip to SkillMotion conversion fidelity."""
import filecmp
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np

from middle_architecture.gmt_motion_adapter import GmtMotionAdapter
from middle_architecture.skill_motion import load_skillmotion
from middle_architecture.source_adapters.qpos_clip import qvel_from_gmt_motion
from task_plan.skill_registry import SkillRegistry


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS = REPO_ROOT / "configs" / "skills.yaml"
LIBRARY = REPO_ROOT / "skillmotion_library"


def assert_dir_equal(left: Path, right: Path) -> None:
    comparison = filecmp.dircmp(str(left), str(right))
    if comparison.left_only or comparison.right_only or comparison.diff_files:
        raise AssertionError(
            f"idempotence mismatch: left_only={comparison.left_only} "
            f"right_only={comparison.right_only} diff_files={comparison.diff_files}"
        )
    for name in comparison.common_dirs:
        assert_dir_equal(left / name, right / name)


registry = SkillRegistry.from_yaml(str(SKILLS))
adapter = GmtMotionAdapter(".")

assert LIBRARY.exists(), "skillmotion_library missing; run conversion script first"
assert len(registry.skills) == 6, len(registry.skills)

for skill_name in sorted(registry.skills.keys()):
    spec = registry.get(skill_name)
    source_motion = adapter.load(spec.motion_file)
    converted = load_skillmotion(str(LIBRARY), skill_name)

    assert converted.source.type == "qpos_clip"
    assert converted.source.original_asset == spec.motion_file
    assert converted.boundaries.default_start_frame == spec.default_start_frame
    assert converted.boundaries.default_end_frame == spec.default_end_frame
    assert converted.qpos.shape == (source_motion.num_frames, 7 + source_motion.dof_pos.shape[1])
    assert converted.qvel.shape == (source_motion.num_frames, 6 + source_motion.dof_pos.shape[1])

    assert np.array_equal(converted.root_pos, source_motion.root_pos), skill_name
    assert np.array_equal(converted.root_rot, source_motion.root_rot), skill_name
    assert np.array_equal(converted.dof_pos, source_motion.dof_pos), skill_name
    if source_motion.local_body_pos is not None:
        assert np.array_equal(converted.local_body_pos, source_motion.local_body_pos), skill_name

    expected_qvel = qvel_from_gmt_motion(source_motion)
    max_abs = float(np.max(np.abs(converted.qvel - expected_qvel)))
    assert max_abs <= 1e-6, (skill_name, max_abs)
    print(f"{skill_name}: qpos bit-identical, qvel max_abs={max_abs:.3e}")

with tempfile.TemporaryDirectory() as tmp:
    tmp_root = Path(tmp)
    out_a = tmp_root / "a"
    out_b = tmp_root / "b"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "convert_qpos_clips_to_skillmotion.py"),
        "--skills",
        str(SKILLS),
        "--output",
        str(out_a),
    ]
    subprocess.check_call(cmd, cwd=str(REPO_ROOT))
    cmd[cmd.index(str(out_a))] = str(out_b)
    subprocess.check_call(cmd, cwd=str(REPO_ROOT))
    assert_dir_equal(out_a, out_b)
    print("idempotent conversion OK")

print("QposClipAdapter validation passed.")
