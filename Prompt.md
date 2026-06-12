# Project Prompt: CHOREO Runtime Upgrade

## Goal

Upgrade the existing HumaSkill framework into **CHOREO**: a source-agnostic, tracker-aware, and recovery-aware language-to-execution runtime for long-horizon humanoid skills.

The first implementation phase **extends the existing framework; it does not rewrite it**. The current three-layer pipeline (`task_plan` → `middle_architecture` → `low_level_execution`) stays the execution backbone. CHOREO adds standardized interfaces *around* it:

- **SkillMotion** — a standardized humanoid skill motion object (identity, source, role, trajectory, boundary metadata, motion features, semantic metadata, tracking metadata, recovery metadata).
- **SourceAdapter** — converters from heterogeneous motion sources (qpos clips first; RL rollouts, diffusion output, teleop demos later) into SkillMotion.
- **TrackerAdapter + TrackerSpec** — a unified wrapper interface around existing trackers (GMT first) that preserves their internal policy code and describes their capabilities declaratively.
- **CanonicalRobotState, CanonicalReference, CanonicalAction** — canonical runtime objects that decouple the composition layer from any single tracker's data conventions.
- **Tracker-aware motion composition** — matching and transition planning that consult SkillMotion features and TrackerSpec entry/exit conditions instead of raw pkl frames only.
- **Recovery-aware execution loop** — an execution monitor and recovery manager (rule-based and log-only in the first version) wrapping the existing orchestrator loop.

### Target runtime flow

```text
Language or predefined skill sequence
→ Structured skill specification
→ SkillMotion library lookup
→ State-aware entry matching
→ Tracker-aware transition repair
→ TrackerAdapter execution
→ Execution monitor
→ Recovery manager
→ Re-entry matching
```

## Non-Goals (for the first implementation phase)

These are explicitly **later extensions**, not part of the first milestone set:

- Online RL policy execution (`RLPolicyRolloutAdapter`, online `SkillPolicy`)
- Multi-tracker handoff and tracker handoff contracts
- Learning-based transition inpainting
- Full LLM planner integration (language → structured skill specification)
- `DiffusionMotionAdapter`, `TeleopDemoAdapter`, `RecoveryMotionAdapter`
- Active recovery control (first recovery manager is rule-based event logging only)
- Transition and recovery benchmarks
- Training or fine-tuning any tracking policy
- Real hardware deployment

## Hard Constraints

1. **Existing qpos clips must keep working.** The 8 GMT `.pkl` motions in `assets/motions/` remain valid inputs throughout the upgrade.
2. **Current motion registry support must remain.** `configs/skills.yaml` + `task_plan/skill_registry.py` (`SkillSpec`) stay functional; the old registry path is removed only after the new path is fully validated — and removal itself is out of scope for this phase.
3. **Existing scripts must keep working.** `scripts/run_harness_sequence.py` and `scripts/run_single_gmt_motion.py` with their current arguments must behave identically when the SkillMotion path is disabled.
4. **No changes to GMT tracker policy internals.** `GMTTrackingRunner`'s control loop, observation construction, and the TorchScript policy are wrapped by `TrackerAdapter`, never edited for CHOREO behavior.
5. **Single-episode execution model is preserved.** Segments continue to execute in one persistent MuJoCo episode without physics resets between segments.
6. **Existing validation suite must keep passing** after every milestone (`scripts/validation/*.py` plus the full demo sequence run).
7. **Output schema is additive only.** `result.json`, `run_summary.json`, `execution_log.json`, and `summary_metrics.json` may gain new fields/blocks but must not lose or rename existing ones.
8. **Large arrays live in `.npy`/`.npz`; YAML stores metadata and paths only.**
9. **New interfaces are typed and YAML schemas are validated on load.**

## Existing System Assumptions

The current framework (validated, last full run 2026-06-10 — see `Documentation.md`) already provides:

- **qpos motion clips**: GMT pkl format (`fps`, `root_pos (N,3)`, `root_rot (N,4, xyzw)`, `dof_pos (N,23)`, `local_body_pos (N,38,3)`); velocities are derived by differentiation with window-19 smoothing.
- **Skill sequence execution**: `HarnessOrchestrator.execute()` runs stabilization → skills → transitions in one MuJoCo episode.
- **Motion registry**: `configs/skills.yaml` → `SkillRegistry`/`SkillSpec` (motion file, default frames, fps, optional per-skill `matching_mode`).
- **State-aware matching**: `MotionMatcher` with `static` and `pose_search` modes, configured in `configs/harness.yaml: matching`.
- **Transition planning**: `TransitionRegistry` (fallback specs in `configs/transitions.yaml`) + runtime `TransitionPlanner` (bridge vs. short Hermite decided from live `RobotState`) + `TransitionBuilder` (interpolation/bridge reference generation, velocity-aware Hermite, reanchoring).
- **Tracker execution**: `GMTTrackingRunner` (50 Hz control, decimation 20, 20-frame proprio history, 20-point future mimic obs, future-reference lookahead, fall detection, initial stand-ready stabilization, first-second diagnostics).
- **Result logging**: per-segment `result.json` (metrics, transition plans, diagnostics), plus run-level `run_summary.json`, `execution_log.json`, `summary_metrics.json` under `outputs/<task_id>/`.

## New Runtime Direction

CHOREO treats every motion — regardless of where it came from — as a `SkillMotion` with a declared **source** (where it came from: `qpos_clip`, `rl_rollout`, `diffusion_generated`, `teleop_demo`, `manual_clip`, `optimized_motion`) and a declared **role** (what it does at runtime: `role.skill_type` such as `locomotion` / `upper_body_gesture` / `stabilization` / `recovery`, and `role.recovery_tag` such as `normal` / `dynamic` / `high_risk` / `safe_reentry`). Recovery is a *role*, not a source type.

Every tracker is described by a `TrackerSpec` and driven through a `TrackerAdapter` that converts between canonical runtime objects and the tracker's native formats. The composition layer (matching, transition planning, monitoring) consumes SkillMotion features and TrackerSpec conditions, so new sources and new trackers plug in without orchestrator rewrites.

## Required Interfaces

### SkillMotion

Standardized motion object containing: identity, source, role, trajectory, boundary metadata, motion features, semantic metadata, tracking metadata, recovery metadata. Preferred on-disk layout:

```text
skillmotion_library/
  skill_name/
    metadata.yaml        # identity, source, role, boundaries, semantics, tracking/recovery metadata, array paths
    qpos.npy             # (N, 30) root_pos + root_quat + dof_pos, or split arrays — schema fixed in Milestone C1
    qvel.npy             # derived velocities
    features.npz         # qvel, root velocity, heading, foot contacts, entry/exit windows
    tracker_audit.json   # per-tracker playability/validation record
```

### SourceAdapter

`SourceAdapter.convert(asset, …) -> SkillMotion`. First concrete adapter: `QposClipAdapter` for the existing GMT pkl clips.

### TrackerSpec + TrackerAdapter

`TrackerSpec` declares: tracker name, tracker type, robot, dof, control frequency, reference type, observation type, action type, action dimension, action scale, joint order, PD gains, normalization files, entry conditions, exit conditions, fallback tracker, fallback skill.

`TrackerAdapter` wraps an existing tracker behind a uniform `track(CanonicalReference, …) -> result` interface without modifying tracker internals. First concrete adapter: `GMTTrackerAdapter` wrapping `GMTTrackingRunner`.

### Canonical runtime objects

- `CanonicalRobotState` — superset of the current `RobotState` with explicit conventions (quaternion order, frames, units).
- `CanonicalReference` — superset of the current `ReferenceFrames` with fps, conventions, and optional feature channels.
- `CanonicalAction` — typed action container (joint position targets first) for future multi-tracker support.

## Deliverables

1. Four consistent planning documents: `Prompt.md` (this file), `Plan.md`, `Implement.md`, updated `Documentation.md`.
2. Milestones C1–C7 implemented per `Plan.md`: SkillMotion schema + loader; QposClipAdapter + converted clip library; feature extraction; TrackerSpec/TrackerAdapter for GMT; SkillMotion path integrated behind a config flag; execution monitor + log-only recovery manager; old-vs-new path validation.
3. A `skillmotion_library/` populated from the existing qpos clips.
4. New validation scripts under `scripts/validation/` for every milestone, plus an A/B comparison of the registry path vs. the SkillMotion path.
5. `Documentation.md` kept current as the live project record (decisions, validation results, known issues).

## First Milestone Focus

The first milestone set deliberately stays small and safe:

- qpos clips → SkillMotion conversion (`QposClipAdapter`),
- SkillMotion loading (schema + loader),
- feature extraction (qvel, root velocity, heading, simple foot contact, basic entry/exit windows),
- **one** wrapped tracker (`GMTTrackerAdapter` around the existing GMT runner).

Everything else in the runtime flow reuses today's matcher, transition planner, orchestrator, and logging.

## Done When

- [ ] `SkillMotion` schema is defined, typed, YAML-validated, and round-trips through save/load (`scripts/validation/validate_skillmotion_schema.py` exits 0).
- [ ] All 8 existing qpos clips convert into `skillmotion_library/` entries with numerically faithful trajectories (`scripts/validation/validate_qpos_clip_adapter.py` exits 0).
- [ ] `features.npz` per skill contains qvel, root velocity, heading, foot contact, and entry/exit windows with sane values (`scripts/validation/validate_skillmotion_features.py` exits 0).
- [ ] `GMTTrackerAdapter` + `TrackerSpec` drive the existing runner with bit-equivalent or tolerance-equivalent results vs. direct runner calls (`scripts/validation/validate_tracker_adapter_parity.py` exits 0).
- [ ] The full demo sequence (`walk_forward → kick_leg → crouch_down → stand_up`) runs successfully through **both** the old registry path and the new SkillMotion path, with the SkillMotion path within agreed metric tolerances (`scripts/validation/validate_skillmotion_pipeline_parity.py` exits 0).
- [ ] Execution monitor emits rule-based events and the recovery manager logs (but does not act on) recovery decisions in `result.json` / `recovery_events.json` (`scripts/validation/validate_execution_monitor.py` exits 0).
- [ ] The pre-existing validation suite still passes and the old path's `summary_metrics.json` is unchanged within run-to-run noise.
- [ ] Every milestone's decisions and validation outputs are recorded in `Documentation.md`.
