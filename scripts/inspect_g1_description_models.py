"""Inspect MuJoCo/URDF models under model/g1_description for motion compatibility."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = PROJECT_ROOT / "model" / "g1_description"
TARGET_QPOS_DIM = 30
TARGET_ACTION_DIM = 23


@dataclass(frozen=True)
class LoadedXmlInfo:
    """Summary of a MuJoCo XML that loaded successfully."""

    path: Path
    nq: int
    nv: int
    nu: int
    njnt: int
    nbody: int
    joint_names: list[str]
    actuator_names: list[str]


@dataclass(frozen=True)
class FailedXmlInfo:
    """Summary of a MuJoCo XML load failure."""

    path: Path
    error: str


def rel(path: Path) -> str:
    """Return a stable project-relative path string."""
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def object_names(mujoco: Any, model: Any, object_type: Any, count: int) -> list[str]:
    """Return named MuJoCo objects, using generated placeholders for unnamed objects."""
    names: list[str] = []
    for index in range(count):
        name = mujoco.mj_id2name(model, object_type, index)
        names.append(name if name else f"<unnamed:{index}>")
    return names


def inspect_xml(path: Path, mujoco: Any) -> LoadedXmlInfo:
    """Load one XML file and extract model dimensions and object names."""
    model = mujoco.MjModel.from_xml_path(str(path))
    return LoadedXmlInfo(
        path=path,
        nq=int(model.nq),
        nv=int(model.nv),
        nu=int(model.nu),
        njnt=int(model.njnt),
        nbody=int(model.nbody),
        joint_names=object_names(mujoco, model, mujoco.mjtObj.mjOBJ_JOINT, int(model.njnt)),
        actuator_names=object_names(
            mujoco,
            model,
            mujoco.mjtObj.mjOBJ_ACTUATOR,
            int(model.nu),
        ),
    )


def rank_loaded_model(info: LoadedXmlInfo) -> tuple[int, int, str]:
    """Rank candidate XMLs by Task 08A compatibility rules."""
    qpos_match = info.nq == TARGET_QPOS_DIM
    action_match = info.nu == TARGET_ACTION_DIM
    if qpos_match and action_match:
        tier = 0
    elif qpos_match:
        tier = 1
    elif action_match:
        tier = 2
    else:
        tier = 3
    return (tier, abs(info.nq - TARGET_QPOS_DIM), rel(info.path))


def print_loaded_xml(info: LoadedXmlInfo) -> None:
    """Print a loadable XML summary in the requested format."""
    print(f"file path: {rel(info.path)}")
    print(f"  nq: {info.nq}")
    print(f"  nv: {info.nv}")
    print(f"  nu: {info.nu}")
    print(f"  njnt: {info.njnt}")
    print(f"  nbody: {info.nbody}")
    print(f"  joint count: {len(info.joint_names)}")
    print(f"  actuator count: {len(info.actuator_names)}")
    print(f"  joint names: {info.joint_names}")
    print(f"  actuator names: {info.actuator_names}")
    print(f"  qpos_match: {info.nq == TARGET_QPOS_DIM}")
    print(f"  action_match: {info.nu == TARGET_ACTION_DIM}")


def main() -> int:
    """Inspect all XML and URDF files in the TextOp G1 model folder."""
    try:
        import mujoco
    except ImportError:
        print("MuJoCo is not installed. Install with: python -m pip install mujoco")
        return 0

    xml_files = sorted(MODEL_DIR.rglob("*.xml")) if MODEL_DIR.exists() else []
    urdf_files = sorted(MODEL_DIR.rglob("*.urdf")) if MODEL_DIR.exists() else []

    print(f"Inspected folder: {rel(MODEL_DIR)}")
    print(f"XML file count: {len(xml_files)}")
    print(f"URDF file count: {len(urdf_files)}")

    loaded: list[LoadedXmlInfo] = []
    failed: list[FailedXmlInfo] = []

    print("\nXML files:")
    for path in xml_files:
        try:
            info = inspect_xml(path, mujoco)
            loaded.append(info)
            print_loaded_xml(info)
        except Exception as exc:  # noqa: BLE001 - continue inspecting all models.
            error = f"{type(exc).__name__}: {exc}"
            failed.append(FailedXmlInfo(path=path, error=error))
            print(f"file path: {rel(path)}")
            print(f"  load error: {error}")

    print("\nURDF files:")
    for path in urdf_files:
        print(f"file path: {rel(path)}")
        print("  file type: URDF")
        print("  note: recorded only, not loaded as MuJoCo XML")

    print("\nBest matching model:")
    if loaded:
        best = sorted(loaded, key=rank_loaded_model)[0]
        print(f"  path: {rel(best.path)}")
        print(f"  nq: {best.nq}")
        print(f"  nu: {best.nu}")
        print(f"  qpos_match: {best.nq == TARGET_QPOS_DIM}")
        print(f"  action_match: {best.nu == TARGET_ACTION_DIM}")
    else:
        print("  path: none")

    if failed:
        print("\nFailed XML files:")
        for item in failed:
            print(f"  {rel(item.path)}: {item.error}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
