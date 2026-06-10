#!/usr/bin/env python3
"""
Inspect a g1-moves pretrained ONNX policy and its paired NPZ reference file.

Example:
python scripts/inspect_g1moves_policy.py \
  --onnx external/g1-moves-data/dance/B_DadDance/policy/B_DadDance_policy.onnx \
  --npz external/g1-moves-data/dance/B_DadDance/training/B_DadDance.npz
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import onnxruntime as ort


def check_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{label} file not found: {path}")


def format_shape(shape) -> str:
    return "[" + ", ".join(str(dim) for dim in shape) + "]"


def inspect_onnx(onnx_path: Path) -> None:
    print("=" * 80)
    print("ONNX POLICY")
    print("=" * 80)
    print(f"path: {onnx_path}")

    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])

    print("\nInputs:")
    for idx, inp in enumerate(session.get_inputs()):
        print(f"  [{idx}] name={inp.name}")
        print(f"      shape={format_shape(inp.shape)}")
        print(f"      type={inp.type}")

    print("\nOutputs:")
    for idx, out in enumerate(session.get_outputs()):
        print(f"  [{idx}] name={out.name}")
        print(f"      shape={format_shape(out.shape)}")
        print(f"      type={out.type}")


def inspect_npz(npz_path: Path) -> None:
    print("\n" + "=" * 80)
    print("NPZ REFERENCE / TRAINING FILE")
    print("=" * 80)
    print(f"path: {npz_path}")

    data = np.load(npz_path, allow_pickle=True)

    keys = list(data.keys())
    print(f"\nnum_keys: {len(keys)}")

    for key in keys:
        value = data[key]
        if isinstance(value, np.ndarray):
            print(f"  {key}: shape={value.shape}, dtype={value.dtype}")
        else:
            print(f"  {key}: type={type(value)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect g1-moves ONNX policy inputs/outputs and NPZ contents."
    )
    parser.add_argument(
        "--onnx",
        type=Path,
        required=True,
        help="Path to g1-moves ONNX policy.",
    )
    parser.add_argument(
        "--npz",
        type=Path,
        required=True,
        help="Path to paired g1-moves NPZ file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        check_file(args.onnx, "ONNX")
        check_file(args.npz, "NPZ")

        inspect_onnx(args.onnx)
        inspect_npz(args.npz)

        print("\n" + "=" * 80)
        print("INSPECTION DONE")
        print("=" * 80)
        return 0

    except Exception as exc:
        print("\n[ERROR] Inspection failed.")
        print(exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
