"""Validate GMT runtime assets are resolved from the current HumaSkill project."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import yaml

from low_level_execution.gmt_tracking_runner import GMTTrackingRunner


CONFIG_PATH = Path("configs/harness.yaml")

with CONFIG_PATH.open("r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

gmt_config = config.get("gmt", {})
assert gmt_config.get("model_path"), "configs/harness.yaml must define gmt.model_path"
assert gmt_config.get("policy_path"), "configs/harness.yaml must define gmt.policy_path"

runner = GMTTrackingRunner(
    gmt_root=gmt_config["root"],
    robot=gmt_config.get("robot", "g1"),
    device=gmt_config.get("device", "auto"),
    model_path=gmt_config.get("model_path"),
    policy_path=gmt_config.get("policy_path"),
)

model_path = runner._resolve_model_path()
policy_path = runner._resolve_policy_path()

repo_root = Path.cwd().resolve()
def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


assert model_path.exists(), f"model_path does not exist: {model_path}"
assert policy_path.exists(), f"policy_path does not exist: {policy_path}"
assert _is_relative_to(model_path, repo_root), f"model_path must be inside project: {model_path}"
assert _is_relative_to(policy_path, repo_root), f"policy_path must be inside project: {policy_path}"
assert policy_path.name == "pretrained.pt", policy_path

print("Local MuJoCo model:", model_path)
print("Local GMT policy:", policy_path)
print("\nAll assertions passed.")

