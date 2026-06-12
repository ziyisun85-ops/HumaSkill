"""Run old registry path and SkillMotion path, then compare decisions and metrics."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_CONFIG = REPO_ROOT / "configs" / "harness.yaml"
SEQUENCE = REPO_ROOT / "configs" / "sequences" / "demo_walk_kick_crouch_stand.yaml"
SKILLS = REPO_ROOT / "configs" / "skills.yaml"
TRANSITIONS = REPO_ROOT / "configs" / "transitions.yaml"
OUTPUT_ROOT = REPO_ROOT / "outputs" / "choreo_pipeline_parity"
TASK_ID = "demo_walk_kick_crouch_stand"


def run_path(name: str, skillmotion_enabled: bool) -> Path:
    output_root = OUTPUT_ROOT / name
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    with open(BASE_CONFIG, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    config["runtime"]["output_root"] = str(output_root)
    config.setdefault("skillmotion", {})
    config["skillmotion"]["enabled"] = skillmotion_enabled
    config["skillmotion"]["library_root"] = "skillmotion_library"
    config["skillmotion"]["tracker_spec"] = "configs/trackers/gmt_g1.yaml"

    config_path = OUTPUT_ROOT / f"{name}_harness.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    subprocess.check_call(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "run_harness_sequence.py"),
            "--config",
            str(config_path),
            "--sequence",
            str(SEQUENCE),
            "--skills",
            str(SKILLS),
            "--transitions",
            str(TRANSITIONS),
        ],
        cwd=str(REPO_ROOT),
    )
    return output_root / TASK_ID


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def segment_result(run_dir: Path, segment_id: str):
    return load_json(run_dir / segment_id / "result.json")


subprocess.check_call(
    [
        sys.executable,
        str(REPO_ROOT / "scripts" / "convert_qpos_clips_to_skillmotion.py"),
        "--skills",
        str(SKILLS),
        "--output",
        str(REPO_ROOT / "skillmotion_library"),
    ],
    cwd=str(REPO_ROOT),
)

registry_dir = run_path("registry", False)
skillmotion_dir = run_path("skillmotion", True)

registry_summary = load_json(registry_dir / "run_summary.json")
skillmotion_summary = load_json(skillmotion_dir / "run_summary.json")
assert registry_summary["success"] is True, registry_summary
assert skillmotion_summary["success"] is True, skillmotion_summary
assert registry_summary["num_segments"] == skillmotion_summary["num_segments"] == 9

registry_log = load_json(registry_dir / "execution_log.json")
skillmotion_log = load_json(skillmotion_dir / "execution_log.json")
registry_ids = [row["segment_id"] for row in registry_log]
skillmotion_ids = [row["segment_id"] for row in skillmotion_log]
assert registry_ids == skillmotion_ids, (registry_ids, skillmotion_ids)

for segment_id in registry_ids:
    old = segment_result(registry_dir, segment_id)
    new = segment_result(skillmotion_dir, segment_id)
    assert old["success"] == new["success"] == True, segment_id
    assert old["num_frames"] == new["num_frames"], segment_id
    assert old.get("start_frame") == new.get("start_frame"), segment_id
    assert old.get("end_frame") == new.get("end_frame"), segment_id
    if old.get("transition_plan") or new.get("transition_plan"):
        assert old.get("transition_plan") == new.get("transition_plan"), segment_id
    assert old["motion_source"]["type"] == "registry", segment_id
    assert new["motion_source"]["type"] == "skillmotion", segment_id

old_metrics = load_json(registry_dir / "summary_metrics.json")
new_metrics = load_json(skillmotion_dir / "summary_metrics.json")

tracking = new_metrics["aggregate_tracking"]
transitions = new_metrics["aggregate_transitions"]
assert tracking["min_success_margin"] > 0.25, tracking["min_success_margin"]
assert transitions["mean_seam_vel_delta"] <= 0.10, transitions["mean_seam_vel_delta"]
assert transitions["mean_peak_jerk"] < 5.0, transitions["mean_peak_jerk"]

tolerances = {
    ("aggregate_tracking", "mean_maje"): 1e-9,
    ("aggregate_tracking", "min_success_margin"): 1e-9,
    ("aggregate_transitions", "mean_seam_vel_delta"): 1e-9,
    ("aggregate_transitions", "mean_peak_jerk"): 1e-9,
}
for (section, key), tolerance in tolerances.items():
    old_value = old_metrics[section][key]
    new_value = new_metrics[section][key]
    diff = abs(float(old_value) - float(new_value))
    assert diff <= tolerance, (section, key, old_value, new_value, diff)

comparison = {
    "registry_output": str(registry_dir),
    "skillmotion_output": str(skillmotion_dir),
    "segments": registry_ids,
    "aggregate_tracking": new_metrics["aggregate_tracking"],
    "aggregate_transitions": new_metrics["aggregate_transitions"],
    "tolerances": {f"{section}.{key}": value for (section, key), value in tolerances.items()},
}
(OUTPUT_ROOT / "comparison.json").write_text(
    json.dumps(comparison, indent=2), encoding="utf-8"
)

print("SkillMotion pipeline parity passed.")
print(f"comparison: {OUTPUT_ROOT / 'comparison.json'}")
