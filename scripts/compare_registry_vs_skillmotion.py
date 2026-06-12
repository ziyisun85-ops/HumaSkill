"""Run and compare the registry and SkillMotion CHOREO paths."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_CONFIG = REPO_ROOT / "configs" / "harness.yaml"
SEQUENCE = REPO_ROOT / "configs" / "sequences" / "demo_walk_kick_crouch_stand.yaml"
SKILLS = REPO_ROOT / "configs" / "skills.yaml"
TRANSITIONS = REPO_ROOT / "configs" / "transitions.yaml"
OUTPUT_ROOT = REPO_ROOT / "outputs" / "choreo_ab"
TASK_ID = "demo_walk_kick_crouch_stand"


def run_sequence(name: str, skillmotion_enabled: bool) -> Path:
    run_root = OUTPUT_ROOT / name
    if run_root.exists():
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    config = yaml.safe_load(BASE_CONFIG.read_text(encoding="utf-8"))
    config["runtime"]["output_root"] = str(run_root)
    config.setdefault("skillmotion", {})
    config["skillmotion"]["enabled"] = bool(skillmotion_enabled)
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
    return run_root / TASK_ID


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def segment_json(run_dir: Path, segment_id: str):
    return load_json(run_dir / segment_id / "result.json")


def tolerance_for(metric: str) -> float:
    if metric in {"success", "start_frame", "end_frame", "transition_decision"}:
        return 0.0
    return 1e-6


def compare_metric(old_value, new_value, metric: str) -> dict:
    if old_value is None and new_value is None:
        return {"pass": True, "diff": 0.0, "tolerance": tolerance_for(metric)}
    if isinstance(old_value, bool) or isinstance(new_value, bool):
        passed = old_value == new_value
        return {"pass": passed, "diff": 0.0 if passed else 1.0, "tolerance": 0.0}
    if old_value is None or new_value is None:
        return {"pass": False, "diff": None, "tolerance": tolerance_for(metric)}
    diff = abs(float(old_value) - float(new_value))
    tol = tolerance_for(metric)
    return {"pass": diff <= tol, "diff": diff, "tolerance": tol}


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

OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
registry_dir = run_sequence("registry", False)
skillmotion_dir = run_sequence("skillmotion", True)

registry_summary = load_json(registry_dir / "run_summary.json")
skillmotion_summary = load_json(skillmotion_dir / "run_summary.json")
registry_log = load_json(registry_dir / "execution_log.json")
skillmotion_log = load_json(skillmotion_dir / "execution_log.json")
registry_ids = [row["segment_id"] for row in registry_log]
skillmotion_ids = [row["segment_id"] for row in skillmotion_log]
if registry_ids != skillmotion_ids:
    raise AssertionError(f"segment id mismatch: {registry_ids} vs {skillmotion_ids}")

rows = []
for segment_id in registry_ids:
    old = segment_json(registry_dir, segment_id)
    new = segment_json(skillmotion_dir, segment_id)
    old_metrics = old.get("metrics") or {}
    new_metrics = new.get("metrics") or {}
    old_tm = old.get("transition_metrics") or {}
    new_tm = new.get("transition_metrics") or {}
    old_plan = old.get("transition_plan") or {}
    new_plan = new.get("transition_plan") or {}

    row = {
        "segment_id": segment_id,
        "success": {
            "registry": old.get("success"),
            "skillmotion": new.get("success"),
            **compare_metric(old.get("success"), new.get("success"), "success"),
        },
        "success_margin": {
            "registry": old_metrics.get("success_margin"),
            "skillmotion": new_metrics.get("success_margin"),
            **compare_metric(
                old_metrics.get("success_margin"),
                new_metrics.get("success_margin"),
                "success_margin",
            ),
        },
        "maje": {
            "registry": old_metrics.get("maje"),
            "skillmotion": new_metrics.get("maje"),
            **compare_metric(old_metrics.get("maje"), new_metrics.get("maje"), "maje"),
        },
        "seam_vel_delta": {
            "registry": old_tm.get("seam_vel_delta"),
            "skillmotion": new_tm.get("seam_vel_delta"),
            **compare_metric(
                old_tm.get("seam_vel_delta"),
                new_tm.get("seam_vel_delta"),
                "seam_vel_delta",
            ),
        },
        "peak_jerk": {
            "registry": old_tm.get("peak_jerk"),
            "skillmotion": new_tm.get("peak_jerk"),
            **compare_metric(old_tm.get("peak_jerk"), new_tm.get("peak_jerk"), "peak_jerk"),
        },
        "auj": {
            "registry": old_tm.get("auj"),
            "skillmotion": new_tm.get("auj"),
            **compare_metric(old_tm.get("auj"), new_tm.get("auj"), "auj"),
        },
        "start_frame": {
            "registry": old.get("start_frame"),
            "skillmotion": new.get("start_frame"),
            **compare_metric(old.get("start_frame"), new.get("start_frame"), "start_frame"),
        },
        "transition_decision": {
            "registry": old_plan.get("decision"),
            "skillmotion": new_plan.get("decision"),
            "pass": old_plan.get("decision") == new_plan.get("decision"),
            "diff": 0.0 if old_plan.get("decision") == new_plan.get("decision") else 1.0,
            "tolerance": 0.0,
        },
    }
    row["pass"] = all(
        value.get("pass", True)
        for key, value in row.items()
        if isinstance(value, dict)
    )
    rows.append(row)

aggregate = {
    "registry_success": registry_summary["success"],
    "skillmotion_success": skillmotion_summary["success"],
    "all_rows_pass": all(row["pass"] for row in rows),
}
comparison = {
    "registry_output": str(registry_dir),
    "skillmotion_output": str(skillmotion_dir),
    "aggregate": aggregate,
    "rows": rows,
}
comparison_path = OUTPUT_ROOT / "comparison.json"
comparison_path.write_text(json.dumps(comparison, indent=2), encoding="utf-8")

md_lines = [
    "# CHOREO Registry vs SkillMotion Comparison",
    "",
    f"- Registry output: `{registry_dir}`",
    f"- SkillMotion output: `{skillmotion_dir}`",
    f"- Overall pass: `{aggregate['all_rows_pass']}`",
    "",
    "| Segment | Pass | Success | Margin Δ | MAJE Δ | Seam Δ | Peak jerk Δ | AUJ Δ | Start | Decision |",
    "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
]
for row in rows:
    decision = row["transition_decision"]["registry"] or ""
    md_lines.append(
        "| {segment} | {passed} | {success} | {margin:.3e} | {maje:.3e} | {seam:.3e} | {jerk:.3e} | {auj:.3e} | {start} | {decision} |".format(
            segment=row["segment_id"],
            passed="yes" if row["pass"] else "no",
            success="yes" if row["success"]["pass"] else "no",
            margin=float(row["success_margin"]["diff"] or 0.0),
            maje=float(row["maje"]["diff"] or 0.0),
            seam=float(row["seam_vel_delta"]["diff"] or 0.0),
            jerk=float(row["peak_jerk"]["diff"] or 0.0),
            auj=float(row["auj"]["diff"] or 0.0),
            start="yes" if row["start_frame"]["pass"] else "no",
            decision=decision,
        )
    )
markdown_path = OUTPUT_ROOT / "comparison.md"
markdown_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

if not aggregate["registry_success"] or not aggregate["skillmotion_success"] or not aggregate["all_rows_pass"]:
    raise SystemExit(1)

print(f"comparison JSON: {comparison_path}")
print(f"comparison Markdown: {markdown_path}")
print("Registry vs SkillMotion comparison passed.")
