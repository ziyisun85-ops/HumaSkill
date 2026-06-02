"""Convert a small set of Unitree G1 retargeted pickle motions to .npy clips."""

from __future__ import annotations

import json
import pickle
import warnings
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "g1-retargeted-motions"
MOTION_DIR = PROJECT_ROOT / "motions"
METADATA_PATH = MOTION_DIR / "metadata.json"
TRAJECTORY_FIELDS = ("dof", "dof_pos", "joint_pos", "joint_positions", "qpos", "pose", "motion")


@dataclass(frozen=True)
class SkillTarget:
    """Preferred filename keywords for one exported HumaSkill motion."""

    skill: str
    include_keywords: tuple[str, ...]
    exclude_keywords: tuple[str, ...] = ()
    notes: str = ""


TARGETS = (
    SkillTarget(
        skill="stand_ready",
        include_keywords=("stand",),
        exclude_keywords=("walk", "lie", "crouch", "skip", "run", "jump", "turn"),
        notes="Closest available standing motion for a ready/idle clip.",
    ),
    SkillTarget(
        skill="arm_wave",
        include_keywords=("swing", "arm"),
        notes="Closest available arm-focused motion; source names use swing/swing arms.",
    ),
    SkillTarget(
        skill="final_pose",
        include_keywords=("stand",),
        exclude_keywords=("walk", "lie", "crouch", "skip", "run", "jump", "turn"),
        notes="Reuses a standing motion as a first final pose clip.",
    ),
)


class PathFixUnpickler(pickle.Unpickler):
    """Load Linux-created pathlib paths on Windows."""

    def find_class(self, module: str, name: str) -> Any:
        if module == "pathlib" and name == "PosixPath":
            return PurePosixPath
        return super().find_class(module, name)


def load_pickle(path: Path) -> Any:
    """Load a pickle file while tolerating PosixPath objects on Windows."""
    with path.open("rb") as file:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return PathFixUnpickler(file).load()


def rel(path: Path) -> str:
    """Return a stable project-relative path string."""
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def iter_motion_records(obj: Any) -> list[tuple[str, dict[str, Any]]]:
    """Return nested motion dictionaries from the observed pickle layout."""
    if isinstance(obj, dict):
        records: list[tuple[str, dict[str, Any]]] = []
        for key, value in obj.items():
            if isinstance(value, dict):
                records.append((str(key), value))
        if records:
            return records
        return [("<root>", obj)]
    return []


def select_motion_field(record: dict[str, Any]) -> tuple[str, np.ndarray]:
    """Pick the first usable 2D trajectory field from a motion record."""
    for field in TRAJECTORY_FIELDS:
        if field in record and hasattr(record[field], "shape"):
            array = np.asarray(record[field])
            if array.ndim == 2 and array.shape[0] > 0 and array.shape[1] > 0:
                return field, array.astype(np.float32, copy=False)

    for field, value in record.items():
        if hasattr(value, "shape"):
            array = np.asarray(value)
            if array.ndim == 2 and array.shape[0] > 0 and array.shape[1] > 0:
                return str(field), array.astype(np.float32, copy=False)

    raise ValueError("No usable 2D trajectory field found")


def score_path(path: Path, target: SkillTarget) -> int:
    """Score how well a source filename matches a target skill."""
    text = path.stem.lower().replace("-", "_")
    if any(keyword not in text for keyword in target.include_keywords):
        return -1
    if any(keyword in text for keyword in target.exclude_keywords):
        return -1
    score = 100
    score -= len(text)
    if "stageii" in text:
        score += 10
    if "accad" in path.as_posix().lower():
        score += 5
    return score


def choose_source(pkl_files: list[Path], target: SkillTarget, used: set[Path]) -> Path:
    """Choose the best available source pickle for a target skill."""
    candidates = [(score_path(path, target), path) for path in pkl_files if path not in used]
    candidates = [(score, path) for score, path in candidates if score >= 0]
    if not candidates:
        for path in pkl_files:
            if path not in used:
                return path
        raise FileNotFoundError("No .pkl files are available for conversion")
    return max(candidates, key=lambda item: (item[0], str(item[1])))[1]


def convert_one(source_path: Path, output_path: Path) -> dict[str, Any]:
    """Convert one source pickle into a .npy motion clip and return metadata."""
    obj = load_pickle(source_path)
    records = iter_motion_records(obj)
    if not records:
        raise ValueError(f"No motion records found in {rel(source_path)}")

    record_name, record = records[0]
    field, array = select_motion_field(record)
    np.save(output_path, array)

    fps_value = record.get("fps", 30)
    fps = int(np.asarray(fps_value).item()) if hasattr(fps_value, "shape") else int(fps_value)
    return {
        "source_record": record_name,
        "field": field,
        "shape": list(array.shape),
        "dtype": str(array.dtype),
        "fps": fps,
        "available_fields": list(record.keys()),
        "has_root_trans_offset": "root_trans_offset" in record,
        "has_root_rot": "root_rot" in record,
    }


def main() -> int:
    """Convert the first small target set into local motion clips."""
    pkl_files = sorted(DATA_DIR.rglob("*.pkl")) if DATA_DIR.exists() else []
    if not pkl_files:
        raise FileNotFoundError(f"No .pkl files found under {rel(DATA_DIR)}")

    MOTION_DIR.mkdir(parents=True, exist_ok=True)
    (MOTION_DIR / ".gitkeep").touch()

    used: set[Path] = set()
    metadata: dict[str, Any] = {
        "robot_name": "unitree_g1",
        "source_dir": rel(DATA_DIR),
        "motion_dir": rel(MOTION_DIR),
        "conversion_notes": (
            "Initial clips export the nested 'dof' trajectory when present. "
            "Root translation and rotation are recorded in metadata but are not fused into qpos yet."
        ),
        "motions": [],
    }

    for target in TARGETS:
        source_path = choose_source(pkl_files, target, used)
        used.add(source_path)
        output_path = MOTION_DIR / f"{target.skill}.npy"
        item = convert_one(source_path, output_path)
        item.update(
            {
                "skill": target.skill,
                "source_file": rel(source_path),
                "output_file": rel(output_path),
                "notes": target.notes,
            }
        )
        metadata["motions"].append(item)

    METADATA_PATH.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print(f"Number of converted motions: {len(metadata['motions'])}")
    for item in metadata["motions"]:
        print(f"- skill: {item['skill']}")
        print(f"  source_file: {item['source_file']}")
        print(f"  selected_field: {item['field']}")
        print(f"  output_file: {item['output_file']}")
        print(f"  shape: {item['shape']}")
        print(f"  dtype: {item['dtype']}")
    print(f"Metadata: {rel(METADATA_PATH)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
