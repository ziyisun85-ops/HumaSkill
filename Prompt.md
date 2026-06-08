# Project Prompt: Improve Transition Generation and Semantic Matching

## Objective

Improve the quality of generated transitions between humanoid robot skills and the accuracy of semantic motion matching in the HumaSkill harness. The pipeline executes a fixed demo sequence (`walk_forward → kick_leg → crouch_down → stand_up`) in a single persistent MuJoCo episode using GMT as the tracking backend. The goal is to reduce kinematic discontinuities at transition seams and to activate adaptive frame selection via pose-search matching.

## Current Baseline (as of last full run)

| Metric | Value |
|--------|-------|
| Mean MAJE across segments | 0.0625 |
| Mean seam velocity delta | 0.110 m/s |
| Mean seam acceleration delta | 2.064 m/s² |
| Mean peak jerk | 7.57 |
| Mean AUJ (area under jerk) | 2.01 |
| Worst peak jerk (transition_002) | **22.7** |
| Worst AUJ (transition_002) | **6.03** |
| Worst success margin (skill_003) | **0.284** |

## Problems to Solve

### P1 — Excessive jerk at `transition_002` (kick_leg → crouch_down)
`transitions.yaml` specifies hermite for this transition but the resulting jerk (22.7) is inconsistent with hermite behavior. Either the mode is not applied or tension is too high. This is the highest-priority fix.

### P2 — Bridge post-interp uses stale kinematic state
In `transition_builder.py`, `build_bridge_post()` receives `bridge_exit_state` — currently a `KinematicFrame` derived from the motion file, not the real robot state after tracking the bridge body. This means post-interpolation starts from a fictional pose rather than the robot's actual position, introducing a state mismatch at the body→post seam.

### P3 — Pose-search matching is unused
`harness.yaml` locks `matching.mode = static`. The `pose_search` implementation in `matcher.py` exists but its scoring weights have never been validated against real trajectories. `skill_003_crouch_down` has the worst `success_margin` (0.284) and is the best candidate to benefit from adaptive frame selection.

## Non-Goals

- Rewriting or replacing the three-layer architecture
- Training or fine-tuning the GMT policy
- Adding new skill types beyond the current four
- Real hardware deployment
- Language or NL-based skill planning
- Windows platform verification

## Hard Constraints

- All changes must preserve the single-episode execution model (no episode resets between segments)
- Outputs must remain JSON-serializable in the existing schema (`result.json` per segment, `summary_metrics.json`)
- No modifications to GMT source code in the external repo
- Validation scripts (`validate_matcher.py`, `validate_hermite.py`, `validate_metrics.py`) must still pass after each milestone
- `stop_on_failure: true` must remain the default in `harness.yaml`

## Deliverables

1. `transition_002` peak jerk reduced to < 5.0 (from 22.7)
2. Bridge post-interp updated to accept real `RobotState` from the runner, not kinematic frame
3. `pose_search` scoring weights validated; mode enabled selectively for `skill_003_crouch_down` or globally
4. Updated `summary_metrics.json` from a fresh full-pipeline run reflecting all improvements
5. `Documentation.md` updated with new baseline metrics and design decisions

## Done-When Criteria

- [ ] `python scripts/validate_hermite.py` passes
- [ ] `python scripts/validate_matcher.py` passes
- [ ] `python scripts/validate_metrics.py` passes
- [ ] Full pipeline run completes without fall detection trigger
- [ ] `transition_002` peak_jerk < 5.0 in new `summary_metrics.json`
- [ ] `transition_002` AUJ < 2.0 in new `summary_metrics.json`
- [ ] Mean seam velocity delta ≤ 0.10 m/s across all transitions
- [ ] All segment success margins > 0.25
- [ ] `Documentation.md` reflects updated metrics and design decisions
