# Plan: Transition Generation and Semantic Matching Improvements

## Overview

Four milestones executed sequentially. Run validation after each before proceeding. If validation fails, debug and fix before continuing to the next milestone.

---

## M1 — Fix Hermite Interpolation for `transition_002`

**Objective:** Reduce `transition_002_kick_leg_to_crouch_down` peak jerk from 22.7 to < 5.0 by ensuring hermite interpolation is correctly applied and tension is properly tuned.

**Files likely to change:**
- `configs/transitions.yaml` — update `interpolation_mode` and `hermite_tension` for transition_002; possibly also for transition_003
- `middle_architecture/transition_builder.py` — inspect whether `_build_interp_frames` correctly routes to hermite when `spec.interpolation_mode == "hermite"`; add debug assertion if needed

**Implementation notes:**
- Verify `spec.interpolation_mode` is being read correctly from the YAML-parsed `TransitionSpec` dataclass. Check `transition_registry.py` for how `interpolation_mode` is mapped from YAML to the spec object.
- The jerk spike at transition_002 suggests either: (a) the interpolation_mode field is not propagating from YAML → spec → `_build_interp_frames`, or (b) the hermite tension is too high (tension=0.5 should be low-jerk but needs verification with the actual velocity boundary values).
- Start tension at 0.3 for transition_002. If jerk is still high, inspect whether `_derive_frame_velocity` at the kick_leg exit frame produces unrealistic velocities (kick motions have large joint velocities).
- Use `validate_hermite.py` to confirm hermite boundary conditions before running the full pipeline.

**Acceptance criteria:**
- `transition_002` peak_jerk < 5.0
- `transition_002` AUJ < 2.0
- `transition_002` seam_vel_delta ≤ 0.10

**Validation commands:**
```bash
python scripts/validation/validate_hermite.py
python scripts/run_harness_sequence.py \
  --config configs/harness.yaml \
  --sequence configs/sequences/demo_walk_kick_crouch_stand.yaml \
  --skills configs/skills.yaml \
  --transitions configs/transitions.yaml
# Check outputs/demo_walk_kick_crouch_stand/transition_002_kick_leg_to_crouch_down/result.json
```

---

## M2 — Fix Bridge Post-Interp to Use Real Robot State

**Objective:** `build_bridge_post()` in `transition_builder.py` currently receives a `KinematicFrame` as `bridge_exit_state`. Change the orchestrator to pass the actual `RobotState` read from the runner after the bridge body segment completes.

**Files likely to change:**
- `middle_architecture/harness_orchestrator.py` — after tracking the bridge body segment, call `runner.get_robot_state()` and pass that `RobotState` to `build_bridge_post()` instead of the kinematic frame
- `middle_architecture/transition_builder.py` — `build_bridge_post()` already accepts any state with `root_pos`, `root_quat`, `dof_pos`, `root_lin_vel`, `dof_vel`, `root_ang_vel` attributes; verify `RobotState` provides all of these or add fallback defaults for missing fields

**Implementation notes:**
- In `harness_orchestrator.py`, find the call site for `build_bridge_post()`. Currently the bridge body segment is tracked, then `build_bridge_post` is called — check what state is passed at that point.
- `RobotState` must have `root_lin_vel`, `dof_vel`, `root_ang_vel` for hermite mode. Inspect `robot_state.py` and `gmt_tracking_runner.get_robot_state()` to verify these fields are populated. If `root_ang_vel` is missing from the runner output, derive it from the last two root quaternions at the control rate.
- The fix is localized: no changes to `build_bridge_post()` signature needed, only the call site.

**Acceptance criteria:**
- Bridge post segment seam_vel_delta ≤ 0.10 (currently 0.177)
- Full pipeline run still passes without falls
- Bridge body → bridge post state continuity: first frame of post-interp root_pos matches runner-reported root_pos within 0.01 m

**Validation commands:**
```bash
python scripts/run_harness_sequence.py \
  --config configs/harness.yaml \
  --sequence configs/sequences/demo_walk_kick_crouch_stand.yaml \
  --skills configs/skills.yaml \
  --transitions configs/transitions.yaml
# Check transition_001_walk_forward_to_kick_leg_post/result.json seam_vel_delta
```

---

## M3 — Calibrate and Enable Pose-Search Matching

**Objective:** Validate `pose_search` scoring weights against known poses, then enable it selectively (at minimum for `skill_003_crouch_down`, which has the worst success margin at 0.284).

**Files likely to change:**
- `configs/harness.yaml` — change `matching.mode` to `pose_search` (global) or add per-skill override mechanism
- `middle_architecture/matcher.py` — optionally add per-skill mode override support if global switch is too coarse
- `scripts/validation/validate_matcher.py` — extend to test scoring accuracy against real trajectory states extracted from `result.json` outputs

**Implementation notes:**
- Run `validate_matcher.py` first with current weights to understand score magnitudes for the existing demo segments.
- The current weights (`dof_pos=1.0, root_quat=0.5, velocity=0.3, root_height=0.2`) were chosen heuristically. For crouch_down, `root_height` should be weighted more heavily (crouched vs. standing robot height difference is ~0.3 m, which is the dominant signal).
- If enabling globally causes regressions in walk_forward or kick_leg tracking, add a per-skill `matching_mode` override in `skills.yaml` or `harness.yaml` under the skill spec. This is preferable to a global toggle.
- `search_window: 60` at 30 fps = 2-second search range. For crouch_down this is appropriate. For walk_forward (periodic motion) it may find a phase-shifted frame; keep walk_forward on static mode.

**Acceptance criteria:**
- `python scripts/validation/validate_matcher.py` passes with all assertions
- `skill_003_crouch_down` success_margin improves from 0.284 (or stays ≥ 0.25 if no regression)
- No new falls introduced by pose_search mode
- Score at the known-good frame is lower than the score at a frame 10+ frames away (verified by validate_matcher.py)

**Validation commands:**
```bash
python scripts/validation/validate_matcher.py
python scripts/run_harness_sequence.py \
  --config configs/harness.yaml \
  --sequence configs/sequences/demo_walk_kick_crouch_stand.yaml \
  --skills configs/skills.yaml \
  --transitions configs/transitions.yaml
# Compare skill_003_crouch_down/result.json success_margin vs. baseline 0.284
```

---

## M4 — Full Pipeline Re-Run and Metrics Update

**Objective:** Execute a clean full pipeline run with all M1–M3 changes applied. Capture updated `summary_metrics.json` and verify all done-when criteria from `Prompt.md` are met.

**Files likely to change:**
- `outputs/demo_walk_kick_crouch_stand/summary_metrics.json` — overwritten by re-run
- `outputs/demo_walk_kick_crouch_stand/*/result.json` — overwritten by re-run
- `Documentation.md` — update current state, metrics baseline, known issues

**Implementation notes:**
- Run all three validation scripts first to confirm unit-level correctness, then run the full pipeline.
- If `transition_002` peak_jerk is still above 5.0 after M1 changes, revisit tension tuning before treating M4 as complete.
- Capture metrics in `Documentation.md` immediately after the run while results are fresh.

**Acceptance criteria (all from Prompt.md done-when list):**
- All three validate_*.py scripts pass
- Full pipeline completes without fall detection
- `transition_002` peak_jerk < 5.0
- `transition_002` AUJ < 2.0
- Mean seam_vel_delta ≤ 0.10 across all transitions
- All segment success margins > 0.25
- `Documentation.md` updated

**Validation commands:**
```bash
python scripts/validation/validate_hermite.py
python scripts/validation/validate_matcher.py
python scripts/validation/validate_metrics.py
python scripts/run_harness_sequence.py \
  --config configs/harness.yaml \
  --sequence configs/sequences/demo_walk_kick_crouch_stand.yaml \
  --skills configs/skills.yaml \
  --transitions configs/transitions.yaml
# Review outputs/demo_walk_kick_crouch_stand/summary_metrics.json
```

