import argparse
import pickle
from pathlib import Path


def inspect_motion(path: str):
    motion_path = Path(path)
    if not motion_path.exists():
        raise FileNotFoundError(f"Motion file not found: {motion_path}")

    with open(motion_path, "rb") as f:
        data = pickle.load(f)

    print(f"path: {motion_path}")
    print(f"type: {type(data).__name__}")
    if not isinstance(data, dict):
        return

    print(f"keys: {sorted(data.keys())}")
    for key in ["fps", "root_pos", "root_rot", "dof_pos", "local_body_pos", "link_body_list"]:
        if key not in data:
            print(f"{key}: MISSING")
            continue
        value = data[key]
        shape = getattr(value, "shape", None)
        dtype = getattr(value, "dtype", None)
        if shape is not None:
            print(f"{key}: shape={shape}, dtype={dtype}")
        else:
            print(f"{key}: {value}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("motion_path")
    args = parser.parse_args()
    inspect_motion(args.motion_path)


if __name__ == "__main__":
    main()
