"""YAML and JSON I/O utilities for HumaSkill."""

import json
from pathlib import Path

import yaml


def load_yaml(path: str) -> dict:
    """Read a YAML file and return the parsed dictionary.

    Args:
        path: Path to the YAML file.

    Returns:
        Parsed dictionary from the YAML content.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError: If the YAML content is invalid.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Failed to parse YAML file {path}: {e}")


def save_json(path: str, data) -> None:
    """Write data to a JSON file.

    Args:
        path: Output path for the JSON file.
        data: Data to serialize to JSON (must be JSON-serializable).

    Raises:
        TypeError: If data is not JSON-serializable.
        OSError: If the file cannot be written.
    """
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(path: str) -> dict:
    """Read a JSON file and return the parsed dictionary.

    Args:
        path: Path to the JSON file.

    Returns:
        Parsed dictionary from the JSON content.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the JSON content is invalid.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)
