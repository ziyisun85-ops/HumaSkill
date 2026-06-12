# Implement: Execution Rules for the CHOREO Runtime Upgrade

Instructions for Codex or any coding agent implementing this upgrade. Read `Prompt.md` (goal, constraints) and `Plan.md` (milestones C1–C7) first. `Documentation.md` is the live project record — keep it current.

Document priority on conflict: `Prompt.md` > `Plan.md` > `Implement.md` > `Documentation.md`. Record every conflict and its resolution in `Documentation.md`.

## Execution Discipline

1. **Follow `Plan.md` milestone order** (C1 → C7). Do not start a milestone before the previous one's validation commands all exit 0.
2. **Make small diffs.** Each milestone touches only its "Files likely affected" list. If you need to touch another file, stop and justify it in `Documentation.md` first.
3. **Do not rewrite unrelated modules.** `GMTTrackingRunner`, `TransitionBuilder`, `MotionMatcher`, `TransitionPlanner`, and the existing registry/orchestrator logic are wrapped or given a seam — never restructured for CHOREO.
4. **Preserve backward compatibility.** With `skillmotion.enabled: false` (the default), every existing script, config, and output must behave exactly as before. Keep old registry support (`configs/skills.yaml` + `SkillRegistry`) until the new path is fully validated — and do not remove it even then without an explicit new plan.
5. **Add tests/validation scripts with each milestone.** Every milestone ships its `scripts/validation/validate_*.py` listed in `Plan.md`.
6. **Run validation after each milestone**: the milestone's own commands plus the shared regression gate from `Plan.md` (existing validation scripts + full demo sequence run). All in the `gmt` conda environment.
7. **If validation fails, fix before moving forward.** Never defer a red validation to a later milestone. If the fix requires scope change, see rule 8.
8. **Do not expand scope without updating `Plan.md` and `Documentation.md`** first. Later-extension items (RL adapters, multi-tracker handoff, LLM planning, active recovery, benchmarks) are off-limits in this phase.
9. **Put generated artifacts and logs in predictable locations**:
   - Converted motions: `skillmotion_library/<skill_name>/`
   - Run outputs: `outputs/<task_id>/` (existing layout, additive fields only)
   - Recovery events: `outputs/<task_id>/recovery_events.json`
   - A/B comparison: `outputs/choreo_ab/`
10. **Record every important decision in `Documentation.md`**: what was decided, why, alternatives rejected, validation command outputs (exit codes + key numbers), and files changed — same format as the existing milestone records.
11. **Prefer adapters and wrappers over invasive rewrites.** New capability enters through `SourceAdapter`, `TrackerAdapter`, and one orchestrator seam — not through edits inside existing control flow.

## Coding Rules

- **New interfaces are typed.** Use `@dataclass` with explicit field types (matching existing house style in `middle_architecture/robot_state.py`); type annotations on all public functions. Target Python 3.8 (`gmt` env) — no 3.9+-only syntax (`list[str]`, `X | None`).
- **YAML schemas are validated on load.** Required keys, enum values (`source.type`, `role.skill_type`, `role.recovery_tag`), shape/path consistency. Raise `ValueError` with the offending file path and key, following `SkillRegistry.from_yaml`'s style.
- **Large arrays stay in `.npy` or `.npz` files.** `metadata.yaml` stores metadata and relative paths only — never array payloads.
- **YAML stores metadata and paths;** all numeric trajectory/feature data is referenced, not embedded.
- **TrackerAdapter preserves existing tracker internals.** `GMTTrackerAdapter` converts canonical objects at the boundary and delegates; no edits to `GMTTrackingRunner`'s control loop, observation construction, or policy I/O. The adapter must pass the two-consecutive-`track()` parity test (proprio history and `last_action` are stateful across calls).
- **Recovery manager v1 is rule-based and log-only.** It recommends; it never executes a motion or alters control flow. `stop_on_failure` semantics are unchanged.
- **Conventions are explicit, never assumed.** Quaternion order is a known trap: GMT pkl `root_rot` is `xyzw`; MuJoCo `qpos[3:7]` / `RobotState.root_quat` is `wxyz`. SkillMotion metadata and canonical objects must declare the order they store; converters assert it in validation.
- **Reuse existing primitives**: pkl parsing via `GmtMotionAdapter`/`load_gmt_motion`; velocity derivation matching `_ReferenceSampler._derive_velocities()` (differentiation + window-19 smoothing); reference slicing/interpolation/reanchoring via `reference_ops`; metrics via `middle_architecture/evaluation.py`.
- **Config additions are flag-gated with safe defaults**: `skillmotion.enabled: false`, `execution_monitor.enabled: true` only once C6's validation proves it is log-only.
- **Output schema is additive.** New blocks (`motion_source`, `recovery`, `transition_plan`-style diagnostics) may be added to `result.json`/`summary_metrics.json`; existing fields are never renamed, retyped, or removed.
- **Determinism in validation:** comparisons of decisions (matched frames, transition modes) are exact; comparisons of physics metrics use tolerances calibrated from two same-path runs, as defined in C7.

## Per-Milestone Checklist

For every milestone Cx:

1. Re-read the Cx section of `Plan.md`; confirm the file whitelist.
2. Implement within the whitelist.
3. `python -m py_compile` on all new/changed Python files.
4. Run Cx validation commands; all must exit 0.
5. Run the shared regression gate; all must exit 0, full demo sequence reports all segments `success=True`.
6. Update `Documentation.md`: Cx record (scope, decisions, files changed, validation output), milestone status table, changelog row.
7. Only then proceed to Cx+1.

## Environment

```bash
conda activate gmt          # Python 3.8, CPU torch
cd G:\Code\Python\HumaSkill
```

Platform note: Windows is the working platform here but is not GMT-verified; do not add platform-specific code paths. Use `pathlib` and relative paths anchored at the project root, as the existing modules do.
