# Implement: Codex Execution Instructions

Follow `Plan.md` milestone by milestone. Do not skip ahead. Run the specified validation commands after each milestone and confirm they pass before moving to the next. If validation fails, debug and fix within the current milestone before continuing.

---

## General Rules

- **Scope diffs tightly.** Each milestone touches only the files listed in its "Files likely to change" section. Do not refactor surrounding code unless it is directly blocking the fix.
- **Do not rewrite architecture.** The three-layer design (task plan → middle architecture → low level execution) is fixed. Changes are confined to config values, method implementations, and call sites.
- **Validate after each milestone.** Run the commands exactly as written in `Plan.md`. Do not proceed if a validation fails.
- **Debug before continuing.** If validation fails, read the error, trace it to the root cause, fix it, and re-run validation. Do not accumulate failures across milestones.
- **Update `Documentation.md` after M2 and M4.** After M2 (bridge fix) and after M4 (full re-run), update the relevant sections of `Documentation.md`: current state, known issues, latest validation results.

---

## M1 — Fix Hermite Interpolation for `transition_002`

### Step 1: Check interpolation_mode propagation

Read `middle_architecture/transition_registry.py` and find where `TransitionSpec` is constructed from the YAML dict. Confirm `interpolation_mode` and `hermite_tension` fields are being set (not left as `None` or a default that overrides YAML values).

Read `middle_architecture/transition_builder.py`, method `_build_interp_frames`. Confirm the conditional `if spec.interpolation_mode == "hermite"` is reachable and that `spec.hermite_tension` is passed through to `hermite_interpolate_reference_frames`.

If either is broken, fix it. This is the most likely root cause of the jerk spike.

### Step 2: Tune tension for transition_002

In `configs/transitions.yaml`, find the `kick_leg → crouch_down` entry. If `interpolation_mode` is missing, add it as `hermite`. Set `hermite_tension: 0.3`.

Rationale: kick_leg has large joint velocities at exit. Lower tension reduces overshoot in the hermite cubic without changing endpoint positions or velocities.

### Step 3: Run unit validation

```bash
python scripts/validation/validate_hermite.py
```

Confirm boundary conditions hold (first and last frames match endpoints) and C1 continuity is preserved.

### Step 4: Run pipeline and inspect transition_002

```bash
python scripts/run_harness_sequence.py \
  --config configs/harness.yaml \
  --sequence configs/sequences/demo_walk_kick_crouch_stand.yaml \
  --skills configs/skills.yaml \
  --transitions configs/transitions.yaml
```

Read `outputs/demo_walk_kick_crouch_stand/transition_002_kick_leg_to_crouch_down/result.json`. Check `metrics.peak_jerk` < 5.0 and `transition_metrics.auj` < 2.0.

If still failing: reduce tension further to 0.1 and re-run, OR inspect whether `_derive_frame_velocity` at the kick exit frame returns velocities > 5 m/s (unrealistic for root). If so, clamp derived velocities at a reasonable bound (e.g., 3 m/s norm) before passing to hermite.

---

## M2 — Fix Bridge Post-Interp to Use Real Robot State

### Step 1: Find the bridge post call site

Read `middle_architecture/harness_orchestrator.py`. Find the code block that:
1. Tracks the bridge body segment via `runner.track(bridge_body_segment.reference_frames)`
2. Calls `transition_builder.build_bridge_post(spec, <state>, next_skill_spec)`

Identify what `<state>` is currently. It will be either a `KinematicFrame` (the bridge motion's exit frame) or a `RobotState`.

### Step 2: Insert runner state read

Immediately after `runner.track(bridge_body_segment.reference_frames)` returns, add:

```python
bridge_exit_state = runner.get_robot_state()
```

Pass `bridge_exit_state` (a `RobotState`) to `build_bridge_post()` instead of the current kinematic value.

### Step 3: Verify RobotState has required fields

Read `low_level_execution/gmt_tracking_runner.py`, method `get_robot_state()`. Confirm it returns a `RobotState` with `root_lin_vel`, `dof_vel`, and `root_ang_vel`.

If `root_ang_vel` is missing: derive it from the last two root quaternions at the control rate (0.02 s) using the same finite-difference logic already in `transition_builder._derive_angular_velocity_at_frame`. Add the derivation inside `get_robot_state()` if needed.

If `dof_vel` is missing: derive from the last two `dof_pos` readings at control rate.

### Step 4: Validate seam continuity

After the pipeline run, check `transition_001_walk_forward_to_kick_leg_post/result.json`:
- `seam_vel_delta` should drop from 0.177 toward ≤ 0.10
- Segment should still succeed (not fall)

---

## M3 — Calibrate and Enable Pose-Search Matching

### Step 1: Run existing validate_matcher.py

```bash
python scripts/validation/validate_matcher.py
```

Read the output. Understand the score magnitudes at the known-good frame vs. adjacent frames. If scores seem unreasonably large (> 10.0) or flat across the window, the weights need adjustment.

### Step 2: Adjust weights for crouch_down

For `skill_003_crouch_down` (squat), `root_height` is the most discriminative signal. Proposed weight update in `configs/harness.yaml`:

```yaml
matching:
  score_weights:
    dof_pos: 1.0
    root_quat: 0.3
    velocity: 0.2
    root_height: 0.8
```

Rationale: standing vs. crouched height difference (~0.3 m) swamps the DOF and quat signals when searching for the correct squat entry frame.

### Step 3: Enable pose_search selectively

Option A (simpler): Set `matching.mode: pose_search` globally in `configs/harness.yaml`. Walk_forward uses a periodic motion where frame-shift doesn't matter much (phase is looped). Kick_leg, crouch_down, stand_up all benefit from pose alignment.

Option B (safer): Add per-skill `matching_mode` override field to `configs/skills.yaml` skill entries. In `MotionMatcher.select()`, check `skill_spec.matching_mode` first before falling back to the global config. This keeps walk_forward on static and enables pose_search only for crouch_down.

Start with Option A. If it causes a regression in walk_forward (success_margin drops below 0.45), switch to Option B.

### Step 4: Validate

```bash
python scripts/validation/validate_matcher.py
python scripts/run_harness_sequence.py ...
```

Check `skill_003_crouch_down/result.json` success_margin vs. baseline 0.284. Any improvement is a success. Ensure no new falls.

---

## M4 — Full Pipeline Re-Run and Metrics Update

### Step 1: Run all unit validations

```bash
python scripts/validation/validate_hermite.py
python scripts/validation/validate_matcher.py
python scripts/validation/validate_metrics.py
```

All must pass. Fix any failures before proceeding.

### Step 2: Run full pipeline

```bash
python scripts/run_harness_sequence.py \
  --config configs/harness.yaml \
  --sequence configs/sequences/demo_walk_kick_crouch_stand.yaml \
  --skills configs/skills.yaml \
  --transitions configs/transitions.yaml
```

### Step 3: Verify all done-when criteria

Read `outputs/demo_walk_kick_crouch_stand/summary_metrics.json` and check:

| Criterion | Target | Actual |
|-----------|--------|--------|
| transition_002 peak_jerk | < 5.0 | (fill in) |
| transition_002 AUJ | < 2.0 | (fill in) |
| Mean seam_vel_delta | ≤ 0.10 | (fill in) |
| Min success_margin | > 0.25 | (fill in) |
| All segments success | true | (fill in) |

### Step 4: Update Documentation.md

Update the following sections in `Documentation.md`:
- **Current State** — note all improvements applied
- **Latest Validation Results** — paste new aggregate metrics from summary_metrics.json
- **Known Issues** — mark P1, P2, P3 from Prompt.md as resolved if criteria met
- **Open Questions** — update with any new observations

