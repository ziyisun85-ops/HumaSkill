"""Diagnose alignment between G1 PKL motion fields and MuJoCo qpos layout."""

from __future__ import annotations

import json
import pickle
import warnings
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "model" / "g1_description" / "g1_23dof.xml"
SOURCE_METADATA_PATH = PROJECT_ROOT / "motions" / "metadata.json"
QPOS_METADATA_PATH = PROJECT_ROOT / "motions" / "metadata_qpos.json"


class PathFixUnpickler(pickle.Unpickler):
    """Load Linux-created pathlib paths on Windows."""

    def find_class(self, module: str, name: str) -> Any:
        if module == "pathlib" and name == "PosixPath":
            return PurePosixPath
        return super().find_class(module, name)


def rel(path: Path) -> str:
    """Return a stable project-relative path string."""
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_project_path(value: str) -> Path:
    """Resolve a metadata path relative to the project root."""
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def load_pickle(path: Path) -> Any:
    """Load a pickle file while tolerating PosixPath objects on Windows."""
    with path.open("rb") as file:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return PathFixUnpickler(file).load()


def first_motion_record(path: Path) -> tuple[str, dict[str, Any]]:
    """Return the first nested motion record from the observed pickle layout."""
    obj = load_pickle(path)
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, dict):
                return str(key), value
        return "<root>", obj
    raise ValueError(f"Expected dict pickle structure in {rel(path)}, got {type(obj).__name__}")


def quat_wxyz_to_matrix(quat: np.ndarray) -> np.ndarray:
    """Return a rotation matrix for a wxyz quaternion."""
    w, x, y, z = quat / np.linalg.norm(quat)
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )


def upright_score(quat_wxyz: np.ndarray) -> float:
    """Return body z-axis dot world z-axis for a wxyz quaternion."""
    return float(quat_wxyz_to_matrix(quat_wxyz)[2, 2])


def print_model_layout(mujoco: Any, model: Any) -> list[str]:
    """Print MuJoCo qpos layout and return scalar joint names after the freejoint."""
    print("XML qpos layout:")
    print(f"  model: {rel(MODEL_PATH)}")
    print(f"  nq: {model.nq}")
    print(f"  nv: {model.nv}")
    print(f"  nu: {model.nu}")
    print(f"  njnt: {model.njnt}")
    print(f"  nbody: {model.nbody}")
    print("  MuJoCo freejoint qpos quaternion order: wxyz")

    scalar_joint_names: list[str] = []
    for index in range(model.njnt):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, index)
        joint_type = int(model.jnt_type[index])
        qpos_address = int(model.jnt_qposadr[index])
        dof_address = int(model.jnt_dofadr[index])
        print(
            f"  joint[{index:02d}] name={name} type={joint_type} "
            f"qposadr={qpos_address} dofadr={dof_address}"
        )
        if index > 0:
            scalar_joint_names.append(str(name))

    print("Actuator order:")
    for index in range(model.nu):
        actuator_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, index)
        joint_id = int(model.actuator_trnid[index][0])
        joint_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id)
        print(f"  actuator[{index:02d}] name={actuator_name} joint={joint_name}")
    return scalar_joint_names


def diagnose_motion(mujoco: Any, model: Any, item: dict[str, Any], qpos_item: dict[str, Any] | None) -> None:
    """Print PKL and converted-qpos diagnostics for one motion."""
    source_path = resolve_project_path(item["source_file"])
    source_record, record = first_motion_record(source_path)
    root_trans = np.asarray(record["root_trans_offset"], dtype=np.float32)
    root_rot = np.asarray(record["root_rot"], dtype=np.float32)
    dof = np.asarray(record["dof"], dtype=np.float32)
    root_rot_as_wxyz = root_rot[0]
    root_rot_xyzw_to_wxyz = root_rot[0, [3, 0, 1, 2]]

    print(f"\nMotion: {item['skill']}")
    print(f"  source_file: {item['source_file']}")
    print(f"  source_record: {source_record}")
    print(f"  available keys: {list(record.keys())}")
    print(f"  root_trans_offset: shape={root_trans.shape} dtype={root_trans.dtype}")
    print(f"  root_rot: shape={root_rot.shape} dtype={root_rot.dtype}")
    print(f"  dof: shape={dof.shape} dtype={dof.dtype}")
    print(f"  first root_trans_offset: {root_trans[0]}")
    print(f"  first root_rot raw: {root_rot[0]}")
    print(f"  first dof: {dof[0]}")
    print(f"  root translation min: {root_trans.min(axis=0)}")
    print(f"  root translation max: {root_trans.max(axis=0)}")
    print(f"  dof min/max: {float(dof.min())} / {float(dof.max())}")
    norms = np.linalg.norm(root_rot, axis=1)
    print(f"  raw root_rot norm range: {float(norms.min())} / {float(norms.max())}")
    print(f"  upright score if raw is wxyz: {upright_score(root_rot_as_wxyz):.6f}")
    print(f"  upright score if raw is xyzw: {upright_score(root_rot_xyzw_to_wxyz):.6f}")
    print("  quaternion convention guess: xyzw")

    if qpos_item is None:
        print("  converted qpos: missing metadata_qpos entry")
        return

    qpos_path = resolve_project_path(qpos_item["output_file"])
    qpos = np.load(qpos_path)
    data = mujoco.MjData(model)
    data.qpos[:] = qpos[0]
    mujoco.mj_forward(model, data)
    root_body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "pelvis")
    root_body_pos = data.xpos[root_body_id] if root_body_id >= 0 else data.qpos[:3]
    print(f"  converted qpos file: {qpos_item['output_file']}")
    print(f"  first converted qpos[0:7]: {qpos[0, :7]}")
    print(f"  first converted qpos quat norm: {float(np.linalg.norm(qpos[0, 3:7]))}")
    print(f"  MuJoCo data.qpos[0:7] after mj_forward: {data.qpos[:7]}")
    print(f"  pelvis/root body position after mj_forward: {root_body_pos}")
    print(f"  converted qpos upright score: {upright_score(qpos[0, 3:7]):.6f}")


def main() -> int:
    """Run the diagnostic report."""
    try:
        import mujoco
    except ImportError:
        print("MuJoCo is not installed. Install with: python -m pip install mujoco")
        return 0

    model = mujoco.MjModel.from_xml_path(str(MODEL_PATH))
    scalar_joint_names = print_model_layout(mujoco, model)
    source_metadata = json.loads(SOURCE_METADATA_PATH.read_text(encoding="utf-8"))
    qpos_metadata = (
        json.loads(QPOS_METADATA_PATH.read_text(encoding="utf-8"))
        if QPOS_METADATA_PATH.exists()
        else {"motions": []}
    )
    qpos_by_skill = {item["skill"]: item for item in qpos_metadata.get("motions", [])}

    print("\nPKL dof index -> MuJoCo joint name -> qpos address -> actuator name")
    for index, joint_name in enumerate(scalar_joint_names):
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
        qpos_address = int(model.jnt_qposadr[joint_id])
        actuator_name = (
            mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, index)
            if index < model.nu
            else "<none>"
        )
        print(f"  {index:02d} -> {joint_name} -> qpos[{qpos_address}] -> {actuator_name}")

    for item in source_metadata.get("motions", []):
        diagnose_motion(mujoco, model, item, qpos_by_skill.get(item["skill"]))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
