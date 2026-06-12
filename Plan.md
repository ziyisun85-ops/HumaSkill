# Plan: CHOREO Runtime Upgrade Milestones

> Milestones are labeled **C1–C7** to avoid collision with the completed v1 milestones (M0–M5) and improvement-phase milestones (M1–M6) recorded in `Documentation.md`. Execute strictly in order; each milestone must pass its validation commands before the next begins. See `Prompt.md` for goals/constraints and `Implement.md` for execution rules.

## Overview

| Milestone | Title | New behavior visible in runtime? |
|-----------|-------|----------------------------------|
| C1 | SkillMotion schema and loader | No (new files only) |
| C2 | QposClipAdapter + clip conversion | No (offline conversion only) |
| C3 | Feature extraction | No (offline artifacts only) |
| C4 | TrackerSpec + GMTTrackerAdapter | No (wrapper parity only) |
| C5 | SkillMotion path integration (flag-gated, off by default) | Only when flag enabled |
| C6 | Execution monitor + log-only recovery manager | New log blocks only |
| C7 | Old-vs-new path tests and A/B validation | No |

Shared regression gate, run after **every** milestone (all must exit 0):

```bash
conda activate gmt
python scripts/validation/validate_hermite.py
python scripts/validation/validate_matcher.py
python scripts/validation/validate_metrics.py
python scripts/validation/validate_transition_planner.py
python scripts/validation/validate_kick_matching_override.py
python scripts/run_harness_sequence.py --config configs/harness.yaml --sequence configs/sequences/demo_walk_kick_crouch_stand.yaml --skills configs/skills.yaml --transitions configs/transitions.yaml
```

---

## C1 — Define SkillMotion Schema and Loader

**Objective:** A typed, validated `SkillMotion` object with YAML metadata + `.npy`/`.npz` array storage, plus save/load round-trip.

**Scope:**
- Dataclasses: `SkillMotion`, `SkillMotionSource`, `SkillMotionRole`, `SkillMotionBoundaries`, `SkillMotionTrackingMeta`, `SkillMotionRecoveryMeta`.
- `metadata.yaml` schema validation on load (required keys, enum checks for `source.type` and `role.skill_type`/`role.recovery_tag`, array path existence, shape consistency against declared dof/frame counts).
- `save_skillmotion(motion, library_root)` / `load_skillmotion(library_root, name)` implementing the layout:

```text
skillmotion_library/<skill_name>/
  metadata.yaml
  qpos.npy
  qvel.npy
  features.npz
  tracker_audit.json
```

- Canonical conventions documented in the schema docstring: root quaternion order, dof order (GMT g1 23-dof), fps, units.
- `CanonicalReference` minimal definition (fps + root_pos/root_rot/dof_pos + conventions) so later milestones don't redefine it.

**Files likely affected:**
- `middle_architecture/skill_motion.py` (new)
- `middle_architecture/canonical.py` (new, `CanonicalReference` only at this stage)
- `scripts/validation/validate_skillmotion_schema.py` (new)
- `Documentation.md`

**Acceptance criteria:**
- A synthetic SkillMotion saves to a temp library dir and reloads with identical metadata and arrays.
- Invalid metadata (missing key, bad enum, mismatched shape, missing array file) raises a clear `ValueError`.
- Arrays are stored only in `.npy`/`.npz`; `metadata.yaml` contains no array payloads.

**Validation commands:**

```bash
conda activate gmt
python -m py_compile middle_architecture/skill_motion.py middle_architecture/canonical.py
python scripts/validation/validate_skillmotion_schema.py
# + shared regression gate
```

**Risks:** Schema churn in later milestones forcing re-conversion. Mitigation: include `schema_version` in metadata from day one; loaders reject unknown versions explicitly.

**Rollback:** New files only — delete `middle_architecture/skill_motion.py`, `middle_architecture/canonical.py`, and the validation script. No existing module imports them yet.

---

## C2 — QposClipAdapter and Clip Conversion

**Objective:** Convert the existing qpos pkl clips into `skillmotion_library/` entries through the first `SourceAdapter`.

**Scope:**
- `SourceAdapter` abstract base (`convert(...) -> SkillMotion`).
- `QposClipAdapter`: reads GMT pkl via the existing `GmtMotionAdapter`/`load_gmt_motion` (reuse, don't reimplement pkl parsing), derives qvel exactly like the runner's `_ReferenceSampler._derive_velocities()` (differentiation + window-19 smoothing), fills `source.type: qpos_clip` with `original_asset` path, and assigns roles.
- Conversion script `scripts/convert_qpos_clips_to_skillmotion.py`: one library entry **per skill in `configs/skills.yaml`** (6 entries), named after the skill, trajectory = full source clip with `default_start_frame`/`default_end_frame` recorded in boundary metadata. Initial role assignment: `walk_forward: locomotion/normal`, `kick_leg: locomotion/dynamic`, `crouch_down: locomotion/normal`, `stand_up: stabilization/normal`, `stable_stand_bridge: stabilization/safe_reentry (target_safe_state: stand_ready)`, `crouchwalk_bridge: stabilization/normal`.
- `features.npz` and `tracker_audit.json` written as valid placeholders (filled in C3/C4).

**Files likely affected:**
- `middle_architecture/source_adapters/__init__.py`, `base.py`, `qpos_clip.py` (new)
- `scripts/convert_qpos_clips_to_skillmotion.py` (new)
- `skillmotion_library/` (new, generated)
- `scripts/validation/validate_qpos_clip_adapter.py` (new)
- `Documentation.md`

**Acceptance criteria:**
- All 6 registry skills convert without error; `qpos` content (root_pos, root_rot, dof_pos) is bit-identical to the source pkl frames; `qvel` matches the runner's derived velocities within 1e-6.
- Source pkl files and `configs/skills.yaml` are untouched.
- Re-running the conversion is idempotent (overwrites deterministically).

**Validation commands:**

```bash
conda activate gmt
python scripts/convert_qpos_clips_to_skillmotion.py --skills configs/skills.yaml --output skillmotion_library
python scripts/validation/validate_qpos_clip_adapter.py
# + shared regression gate
```

**Risks:** Quaternion-order confusion (pkl `root_rot` is `xyzw`, MuJoCo/RobotState is `wxyz`). Mitigation: SkillMotion metadata declares the stored order explicitly; the validation script asserts it against a known clip.

**Rollback:** Delete `skillmotion_library/` and the new modules/scripts. Nothing in the runtime imports them yet.

---

## C3 — Feature Extraction

**Objective:** Populate `features.npz` with motion features the tracker-aware composition layer will consume.

**Scope:**
- `middle_architecture/feature_extraction.py`: from a SkillMotion trajectory compute
  - `qvel` (already derived in C2; referenced or duplicated into features for one-stop access),
  - root linear velocity (world and heading-local) and root angular velocity,
  - heading (yaw) per frame,
  - simple foot contact per frame from `local_body_pos` foot heights + foot vertical velocity thresholds (kinematic heuristic; thresholds in the extraction config, recorded in metadata),
  - basic entry/exit windows: leading/trailing frame ranges where dof velocity norm and root velocity are below configurable stability thresholds (fallback: fixed first/last 10 frames flagged `low_confidence`).
- Conversion script gains `--features` step (or runs it by default).

**Files likely affected:**
- `middle_architecture/feature_extraction.py` (new)
- `middle_architecture/source_adapters/qpos_clip.py` (call extraction)
- `scripts/convert_qpos_clips_to_skillmotion.py`
- `scripts/validation/validate_skillmotion_features.py` (new)
- `Documentation.md`

**Acceptance criteria:**
- Every library entry's `features.npz` has consistent lengths with the trajectory.
- Sanity checks pass: `walk_forward` shows alternating single-foot contacts; `stable_stand_bridge` shows sustained double contact and a near-zero-velocity entry window; headings are continuous (no 2π jumps after unwrapping).
- Entry/exit windows are recorded in both `features.npz` and `metadata.yaml` boundary metadata.

**Validation commands:**

```bash
conda activate gmt
python scripts/convert_qpos_clips_to_skillmotion.py --skills configs/skills.yaml --output skillmotion_library
python scripts/validation/validate_skillmotion_features.py
# + shared regression gate
```

**Risks:** Kinematic foot-contact heuristics are noisy for dynamic clips (airkick). Mitigation: store per-frame contact *confidence*, not just booleans; nothing downstream hard-depends on contact correctness in this phase.

**Rollback:** Regenerate library without features (C2 placeholders); delete the new module and script.

---

## C4 — TrackerSpec and GMTTrackerAdapter

**Objective:** Wrap the existing GMT runner behind a declarative `TrackerSpec` + uniform `TrackerAdapter` interface without changing tracker policy code.

**Scope:**
- `CanonicalRobotState` and `CanonicalAction` added to `middle_architecture/canonical.py` (CanonicalRobotState mirrors `RobotState` + explicit conventions; CanonicalAction = typed joint-position-target container).
- `low_level_execution/tracker_adapter.py`: `TrackerAdapter` base with `initialize()`, `get_state() -> CanonicalRobotState`, `track(CanonicalReference, ...) -> result`; `GMTTrackerAdapter` converting CanonicalReference ↔ `ReferenceFrames` and delegating to the *unmodified* `GMTTrackingRunner` (including `future_reference_frames` passthrough).
- `configs/trackers/gmt_g1.yaml`: TrackerSpec for GMT — name, type (`general_motion_tracking`), robot (`g1`), dof (23), control frequency (50 Hz), reference type (`kinematic_reference_frames`), observation type (`proprio_history20 + mimic_future20`), action type (`joint_position_target`), action dimension (23), action scale, joint order, PD gains, normalization (explicit scales only: `ang_vel_scale=0.25`, `dof_pos_scale=1.0`, `dof_vel_scale=0.05`), entry conditions (e.g. near-standing or matched reference frame), exit conditions (fall detection thresholds), fallback tracker (`none`), fallback skill (`stable_stand_bridge`). Values sourced from the M0 contract and `configs/harness.yaml` — no invented numbers.
- TrackerSpec loader with schema validation; `tracker_audit.json` per library entry gains a GMT playability record (filled by validation, not hand-written).

**Files likely affected:**
- `middle_architecture/canonical.py`
- `low_level_execution/tracker_adapter.py` (new)
- `configs/trackers/gmt_g1.yaml` (new)
- `scripts/validation/validate_tracker_adapter_parity.py` (new)
- `Documentation.md`

**Acceptance criteria:**
- `GMTTrackingRunner` source is unchanged except (at most) zero-behavior-change refactors explicitly approved in `Documentation.md`.
- Parity test: a short reference segment tracked via `GMTTrackerAdapter` and via direct `GMTTrackingRunner.track()` from the same initialized state produces identical `RunnerTrackResult` content (same frames, same success flag, same final state within 1e-9).
- TrackerSpec loads, validates, and its numeric fields match the M0 contract values.

**Validation commands:**

```bash
conda activate gmt
python -m py_compile low_level_execution/tracker_adapter.py middle_architecture/canonical.py
python scripts/validation/validate_tracker_adapter_parity.py
# + shared regression gate
```

**Risks:** Hidden statefulness (proprio history, `last_action` carried across `track()` calls) breaking parity if the adapter inserts extra calls. Mitigation: adapter is a thin passthrough; parity test covers two consecutive `track()` calls.

**Rollback:** Delete the adapter module, tracker config, and validation script; nothing else references them until C5.

---

## C5 — SkillMotion Path Integration (Flag-Gated)

**Objective:** Run the existing demo sequence end-to-end with motions loaded from `skillmotion_library/` while preserving the old registry path byte-for-byte when the flag is off.

**Scope:**
- `configs/harness.yaml` gains:

```yaml
skillmotion:
  enabled: false            # old registry path remains the default
  library_root: skillmotion_library
  tracker_spec: configs/trackers/gmt_g1.yaml
```

- A motion-source seam in `HarnessOrchestrator` (or a small provider class): when enabled, skill lookups resolve SkillMotion entries and expose trajectories to `MotionMatcher`, `TransitionPlanner`, and `TransitionBuilder` through the same `GMTMotion`/`ReferenceFrames`-compatible view they consume today; when disabled, the current code path executes unchanged.
- Execution goes through `GMTTrackerAdapter` when enabled; direct runner calls when disabled.
- Logging: each segment `result.json` gains a `motion_source` block (`registry` | `skillmotion`, library entry name, source/role) — additive only.
- `scripts/run_harness_sequence.py` gains optional `--motion-source {registry,skillmotion}` override.

**Files likely affected:**
- `configs/harness.yaml`
- `middle_architecture/harness_orchestrator.py` (seam only — minimal diff)
- `middle_architecture/skill_motion.py` (compat view helper)
- `scripts/run_harness_sequence.py`
- `scripts/validation/validate_skillmotion_pipeline_parity.py` (new)
- `Documentation.md`

**Acceptance criteria:**
- Flag **off**: full demo sequence output (`summary_metrics.json`) matches the pre-C5 baseline within run-to-run noise; no new code executes in hot paths (verified by the parity validation asserting identical matcher/transition decisions).
- Flag **on**: all 9 segments succeed; matcher decisions, transition planner decisions, and key metrics (min success margin > 0.25, mean seam velocity delta ≤ 0.10, transition_002 peak jerk < 5.0) hold within tolerance vs. the registry path.
- Old registry path and configs remain fully supported.

**Validation commands:**

```bash
conda activate gmt
python scripts/validation/validate_skillmotion_pipeline_parity.py
python scripts/run_harness_sequence.py --config configs/harness.yaml --sequence configs/sequences/demo_walk_kick_crouch_stand.yaml --skills configs/skills.yaml --transitions configs/transitions.yaml
python scripts/run_harness_sequence.py --config configs/harness.yaml --sequence configs/sequences/demo_walk_kick_crouch_stand.yaml --skills configs/skills.yaml --transitions configs/transitions.yaml --motion-source skillmotion
# + shared regression gate
```

**Risks:** Highest-risk milestone — touching the orchestrator. Mitigation: single seam point, flag default off, parity script run before and after; if the SkillMotion run diverges metrically, fix the library/adapters, not the orchestrator.

**Rollback:** Set `skillmotion.enabled: false` (instant). Code rollback: revert the orchestrator seam commit; C1–C4 artifacts are unaffected.

---

## C6 — Execution Monitor and Recovery Manager Placeholder

**Objective:** Add a rule-based, **log-only** execution monitor and recovery manager around the segment loop.

**Scope:**
- `middle_architecture/execution_monitor.py`: consumes per-segment results + first-second diagnostics and emits typed events — `fall_detected`, `low_success_margin` (< 0.30 warning per the open question in `Documentation.md`), `seam_velocity_exceeded`, `tilt_exceeded`, `tracking_error_high`.
- `middle_architecture/recovery_manager.py`: maps events to *recommended* recovery actions using SkillMotion roles (e.g. fall → recommend `role.skill_type: recovery` / `safe_reentry` entry such as `stable_stand_bridge`, re-entry frame via existing matcher) — **logged only, never executed** in this phase.
- Orchestrator calls monitor + manager after each segment; recommendations written to `outputs/<task_id>/recovery_events.json` and a `recovery` block in each segment `result.json`.
- Thresholds in `configs/harness.yaml: execution_monitor` (new block), defaults chosen from measured values already in `Documentation.md`.

**Files likely affected:**
- `middle_architecture/execution_monitor.py`, `middle_architecture/recovery_manager.py` (new)
- `middle_architecture/harness_orchestrator.py` (post-segment hook, minimal diff)
- `configs/harness.yaml`
- `scripts/validation/validate_execution_monitor.py` (new)
- `Documentation.md`

**Acceptance criteria:**
- A normal full run emits zero or warning-level events and a valid (possibly empty) `recovery_events.json`.
- A synthetic failing state (unit-level, injected `RobotState`/result) produces the expected `fall_detected` event and a `stable_stand_bridge` re-entry recommendation.
- Control flow is unchanged: `stop_on_failure` behavior identical; no recovery motion is executed.

**Validation commands:**

```bash
conda activate gmt
python scripts/validation/validate_execution_monitor.py
python scripts/run_harness_sequence.py --config configs/harness.yaml --sequence configs/sequences/demo_walk_kick_crouch_stand.yaml --skills configs/skills.yaml --transitions configs/transitions.yaml
# + shared regression gate
```

**Risks:** Threshold spam (noisy warnings devaluing the log). Mitigation: start with permissive thresholds from measured runs; record tuning in `Documentation.md`.

**Rollback:** `execution_monitor.enabled: false` config switch; revert the post-segment hook.

---

## C7 — Old-vs-New Path Tests and Validation

**Objective:** A repeatable A/B validation proving the SkillMotion path is a faithful superset of the registry path.

**Scope:**
- `scripts/compare_registry_vs_skillmotion.py`: runs (or consumes outputs of) both paths and writes `outputs/choreo_ab/comparison.json` + a Markdown table: per-segment success, success margins, MAJE, seam velocity delta, peak jerk/AUJ, matcher start frames, transition planner decisions, with per-metric tolerances and pass/fail.
- Consolidated validation entry point `scripts/validation/validate_choreo_suite.py` running all C1–C6 validations in order.
- Documentation pass: `Documentation.md` updated with final A/B table, decisions, and the "how to run the SkillMotion path" section confirmed against reality.

**Files likely affected:**
- `scripts/compare_registry_vs_skillmotion.py` (new)
- `scripts/validation/validate_choreo_suite.py` (new)
- `Documentation.md`

**Acceptance criteria:**
- A/B comparison passes all tolerances; identical matcher/transition decisions in both paths for the demo sequence (or any divergence is explained and accepted in `Documentation.md`).
- `validate_choreo_suite.py` exits 0 and is the single command a future agent runs to verify CHOREO phase 1.
- All `Prompt.md` Done-When boxes can be checked.

**Validation commands:**

```bash
conda activate gmt
python scripts/compare_registry_vs_skillmotion.py
python scripts/validation/validate_choreo_suite.py
# + shared regression gate
```

**Risks:** Run-to-run physics nondeterminism blurring tolerances. Mitigation: compare decisions (frames, modes) exactly and metrics with tolerances calibrated from two same-path runs.

**Rollback:** None needed — read-only comparison tooling.

---

## Later Extensions (explicitly out of scope for C1–C7)

- `RLPolicyRolloutAdapter` — SkillMotion from RL policy rollouts (e.g. recovery policies)
- `DiffusionMotionAdapter` — SkillMotion from diffusion-generated motion
- `TeleopDemoAdapter` — SkillMotion from teleoperation demos
- `RecoveryMotionAdapter` — dedicated ingestion for recovery-role motions
- Online `SkillPolicy` execution (policy-as-skill rather than clip-as-skill)
- Multi-tracker handoff and tracker handoff contracts (entry/exit condition negotiation between TrackerSpecs)
- Learning-based transition inpainting (replacing Hermite/bridge where needed)
- LLM-based structured skill specification (language → skill spec → library lookup)
- Active recovery execution (recovery manager acting, not just logging)
- Transition benchmark and recovery benchmark suites
