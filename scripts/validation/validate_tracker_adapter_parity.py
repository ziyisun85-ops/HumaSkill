"""Validate GMTTrackerAdapter parity with direct GMTTrackingRunner calls."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import yaml

from low_level_execution.gmt_tracking_runner import GMTTrackingRunner
from low_level_execution.tracker_adapter import GMTTrackerAdapter, load_tracker_spec
from middle_architecture.canonical import CanonicalReference
from middle_architecture.gmt_motion_adapter import GmtMotionAdapter
from middle_architecture.reference_ops import slice_motion_to_reference_frames
from middle_architecture.skill_motion import load_skillmotion


REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS_CONFIG = REPO_ROOT / "configs" / "harness.yaml"
TRACKER_SPEC = REPO_ROOT / "configs" / "trackers" / "gmt_g1.yaml"
LIBRARY = REPO_ROOT / "skillmotion_library"


def make_runner(config):
    return GMTTrackingRunner(
        gmt_root=config["gmt"]["root"],
        robot=config["gmt"].get("robot", "g1"),
        device=config["gmt"].get("device", "auto"),
        model_path=config["gmt"].get("model_path"),
        policy_path=config["gmt"].get("policy_path"),
        fall_config=config.get("fall_detection"),
        render=False,
    )


def state_vector(state):
    return np.concatenate(
        [
            np.asarray(state.root_pos, dtype=np.float64),
            np.asarray(state.root_quat, dtype=np.float64),
            np.asarray(state.dof_pos, dtype=np.float64),
            np.asarray(state.root_lin_vel, dtype=np.float64),
            np.asarray(state.root_ang_vel, dtype=np.float64),
            np.asarray(state.dof_vel, dtype=np.float64),
        ]
    )


with open(HARNESS_CONFIG, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

spec = load_tracker_spec(str(TRACKER_SPEC))
assert spec.name == "gmt_g1"
assert spec.tracker_type == "general_motion_tracking"
assert spec.robot == "g1"
assert spec.dof == 23
assert spec.action_dimension == 23
assert abs(spec.control_frequency_hz - 50.0) < 1e-9
assert spec.normalization["ang_vel_scale"] == 0.25
assert spec.normalization["dof_pos_scale"] == 1.0
assert spec.normalization["dof_vel_scale"] == 0.05
print("TrackerSpec loads and matches GMT M0 contract values")

motion_adapter = GmtMotionAdapter(".")
motion = motion_adapter.load("assets/motions/walk_stand.pkl")
first_reference = slice_motion_to_reference_frames(motion, 0, 35)
second_reference = slice_motion_to_reference_frames(motion, 35, 70)

direct_runner = make_runner(config)
adapter_runner = make_runner(config)
direct_runner.initialize()
adapter = GMTTrackerAdapter(adapter_runner, spec)
adapter.initialize()

direct_first = direct_runner.track(first_reference, segment_label="direct_first")
adapter_first = adapter.track(
    CanonicalReference.from_reference_frames(first_reference),
    segment_label="adapter_first",
)
direct_state_first = direct_runner.get_robot_state()
adapter_state_first = adapter.get_state().to_robot_state()

direct_second = direct_runner.track(second_reference, segment_label="direct_second")
adapter_second = adapter.track(
    CanonicalReference.from_reference_frames(second_reference),
    segment_label="adapter_second",
)
direct_state_second = direct_runner.get_robot_state()
adapter_state_second = adapter.get_state().to_robot_state()

for label, direct_result, adapter_result, direct_state, adapter_state in [
    ("first", direct_first, adapter_first, direct_state_first, adapter_state_first),
    ("second", direct_second, adapter_second, direct_state_second, adapter_state_second),
]:
    assert direct_result.success == adapter_result.success, label
    assert direct_result.num_frames == adapter_result.num_frames, label
    assert direct_result.failed_reason == adapter_result.failed_reason, label
    delta = float(np.max(np.abs(state_vector(direct_state) - state_vector(adapter_state))))
    assert delta <= 1e-9, (label, delta)
    print(
        f"{label} track parity OK: success={direct_result.success} "
        f"frames={direct_result.num_frames} final_state_max_abs={delta:.3e}"
    )

if LIBRARY.exists():
    for name in ["walk_forward", "kick_leg", "crouch_down", "stand_up", "stable_stand_bridge", "crouchwalk_bridge"]:
        entry = LIBRARY / name
        if not entry.exists():
            continue
        audit_path = entry / "tracker_audit.json"
        audit = json.loads(audit_path.read_text(encoding="utf-8") or "{}")
        audit["gmt_g1"] = {
            "status": "validated_adapter_parity",
            "validation": "scripts/validation/validate_tracker_adapter_parity.py",
            "reference": "assets/motions/walk_stand.pkl[0:70]",
        }
        audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
        # Round-trip through loader to ensure audit JSON remains valid metadata-adjacent state.
        load_skillmotion(str(LIBRARY), name)
    print("tracker_audit.json updated for existing SkillMotion entries")

print("GMTTrackerAdapter parity validation passed.")
