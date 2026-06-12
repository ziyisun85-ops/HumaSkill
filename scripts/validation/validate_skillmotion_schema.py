"""Validate SkillMotion metadata schema and save/load round-trip."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import yaml

from middle_architecture.skill_motion import (
    SkillMotion,
    SkillMotionBoundaries,
    SkillMotionRole,
    SkillMotionSource,
    load_skillmotion,
    save_skillmotion,
)


def make_motion() -> SkillMotion:
    n = 12
    dof = 23
    root_pos = np.zeros((n, 3), dtype=np.float32)
    root_pos[:, 0] = np.linspace(0.0, 0.2, n, dtype=np.float32)
    root_rot = np.tile(
        np.asarray([[0.0, 0.0, 0.0, 1.0]], dtype=np.float32), (n, 1)
    )
    dof_pos = np.zeros((n, dof), dtype=np.float32)
    qpos = np.concatenate([root_pos, root_rot, dof_pos], axis=1)
    qvel = np.zeros((n, 6 + dof), dtype=np.float32)
    local_body_pos = np.zeros((n, 38, 3), dtype=np.float32)
    return SkillMotion(
        name="synthetic_skill",
        fps=30.0,
        dof=dof,
        qpos=qpos,
        qvel=qvel,
        local_body_pos=local_body_pos,
        source=SkillMotionSource(
            type="qpos_clip",
            original_asset="assets/motions/synthetic.pkl",
            adapter="validate_skillmotion_schema",
        ),
        role=SkillMotionRole(skill_type="locomotion", recovery_tag="normal"),
        boundaries=SkillMotionBoundaries(default_start_frame=1, default_end_frame=10),
        features={"placeholder": np.zeros((n,), dtype=np.float32)},
        tracker_audit={"gmt_g1": {"status": "not_run"}},
    )


def expect_value_error(label, fn):
    try:
        fn()
    except ValueError as exc:
        message = str(exc)
        assert label in message or message, message
        print(f"expected ValueError for {label}: {message}")
        return
    raise AssertionError(f"expected ValueError for {label}")


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    motion = make_motion()
    entry = save_skillmotion(motion, str(root))
    loaded = load_skillmotion(str(root), "synthetic_skill")

    assert loaded.name == motion.name
    assert loaded.schema_version == motion.schema_version
    assert loaded.source.type == "qpos_clip"
    assert loaded.role.skill_type == "locomotion"
    assert loaded.boundaries.default_start_frame == 1
    assert loaded.boundaries.default_end_frame == 10
    assert np.array_equal(loaded.qpos, motion.qpos)
    assert np.array_equal(loaded.qvel, motion.qvel)
    assert np.array_equal(loaded.local_body_pos, motion.local_body_pos)
    assert set(loaded.features.keys()) == {"placeholder"}
    print("round-trip save/load OK")

    metadata = yaml.safe_load((entry / "metadata.yaml").read_text(encoding="utf-8"))
    text = json.dumps(metadata)
    assert "qpos.npy" in text and "qvel.npy" in text and "features.npz" in text
    assert "0.200000" not in text, "metadata should not contain array payloads"
    print("metadata stores paths only")

    bad_missing = root / "bad_missing"
    shutil.copytree(entry, bad_missing)
    raw = yaml.safe_load((bad_missing / "metadata.yaml").read_text(encoding="utf-8"))
    del raw["source"]
    (bad_missing / "metadata.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    expect_value_error("source", lambda: load_skillmotion(str(root), "bad_missing"))

    bad_enum = root / "bad_enum"
    shutil.copytree(entry, bad_enum)
    raw = yaml.safe_load((bad_enum / "metadata.yaml").read_text(encoding="utf-8"))
    raw["source"]["type"] = "unknown_source"
    (bad_enum / "metadata.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    expect_value_error("source.type", lambda: load_skillmotion(str(root), "bad_enum"))

    bad_shape = root / "bad_shape"
    shutil.copytree(entry, bad_shape)
    np.save(bad_shape / "qpos.npy", motion.qpos[:, :-1])
    expect_value_error("qpos width", lambda: load_skillmotion(str(root), "bad_shape"))

    bad_path = root / "bad_path"
    shutil.copytree(entry, bad_path)
    (bad_path / "qvel.npy").unlink()
    expect_value_error("arrays.qvel", lambda: load_skillmotion(str(root), "bad_path"))

print("SkillMotion schema validation passed.")
