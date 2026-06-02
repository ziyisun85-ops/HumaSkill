"""Inspect downloaded Unitree G1 retargeted motion pickle files."""

from __future__ import annotations

import pickle
import warnings
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "g1-retargeted-motions"
MAX_PATHS_TO_PRINT = 50
MAX_FILES_TO_INSPECT = 10


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


def short_repr(value: Any, limit: int = 120) -> str:
    """Return a compact repr preview."""
    text = repr(value)
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def describe_array(name: str, value: Any, indent: str) -> None:
    """Print shape, dtype, and a short 2D first-row preview for an array-like value."""
    array = np.asarray(value)
    print(f"{indent}{name}: type={type(value).__name__}, shape={array.shape}, dtype={array.dtype}")
    if array.ndim == 2 and array.shape[0] > 0:
        preview = np.array2string(array[0, : min(8, array.shape[1])], precision=4)
        print(f"{indent}  first_row[:8]={preview}")


def describe_value(name: str, value: Any, indent: str = "  ", depth: int = 0) -> None:
    """Print a concise structural summary for pickle contents."""
    if hasattr(value, "shape"):
        describe_array(name, value, indent)
        return

    if isinstance(value, dict):
        keys = list(value.keys())
        key_preview = ", ".join(short_repr(key, 60) for key in keys[:8])
        suffix = " ..." if len(keys) > 8 else ""
        print(f"{indent}{name}: dict(len={len(keys)}, keys=[{key_preview}{suffix}])")
        if depth < 2:
            for key in keys[:8]:
                describe_value(str(key), value[key], indent + "  ", depth + 1)
        return

    if isinstance(value, (list, tuple)):
        print(f"{indent}{name}: {type(value).__name__}(len={len(value)})")
        if depth < 2:
            for index, item in enumerate(value[:5]):
                describe_value(f"[{index}]", item, indent + "  ", depth + 1)
        return

    print(f"{indent}{name}: type={type(value).__name__}, value={short_repr(value)}")


def main() -> int:
    """Inspect the available G1 pickle files."""
    pkl_files = sorted(DATA_DIR.rglob("*.pkl")) if DATA_DIR.exists() else []

    print(f"Data directory: {rel(DATA_DIR)}")
    print(f"Total .pkl files: {len(pkl_files)}")
    print(f"First {min(MAX_PATHS_TO_PRINT, len(pkl_files))} .pkl files:")
    for path in pkl_files[:MAX_PATHS_TO_PRINT]:
        print(f"  {rel(path)}")

    print(f"\nInspecting first {min(MAX_FILES_TO_INSPECT, len(pkl_files))} .pkl files:")
    for path in pkl_files[:MAX_FILES_TO_INSPECT]:
        print("\n" + "=" * 80)
        print(f"File: {rel(path)}")
        try:
            obj = load_pickle(path)
            print(f"Python object type: {type(obj).__name__}")
            if isinstance(obj, dict):
                keys = list(obj.keys())
                print(f"Dictionary keys ({len(keys)}):")
                for key in keys[:20]:
                    print(f"  - {short_repr(key, 160)}")
                for key in keys[:5]:
                    describe_value(str(key), obj[key], indent="  ")
            else:
                describe_value("object", obj, indent="  ")
        except Exception as exc:  # noqa: BLE001 - inspection should keep going.
            print(f"ERROR: {type(exc).__name__}: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
