# HumaSkill: Project Review & Improvement Roadmap

## Current State: What Works

| Component | Status |
|---|---|
| 3-layer architecture (task plan / middle / execution) | Solid, clean separation |
| Demo sequence walk→kick→crouch→stand | Fully working (8 segments, all success) |
| Bridge transition (walk→kick via stable_stand_bridge) | Working, split into `_body` + `_post` segments |
| Interpolation transitions (kick→crouch, crouch→stand) | Working (linear lerp + slerp) |
| Closed-loop state: real robot state feeds next transition | Working |
| Per-segment JSON + NPZ output logs | Working |

## Current State: Critical Gaps

| Gap | Impact |
|---|---|
| No quality metrics — MAJE, tracking error, success margin | **Blocks all learning** |
| Linear interpolation has velocity discontinuity at seams | Wastes robot stability |
| MotionMatcher always uses hardcoded frame 0 | Suboptimal skill entry |
| TransitionRegistry raises `KeyError` for unknown pairs | Any new task requires manual YAML |
| No failure recovery — `stop_on_failure=True` only | Brittle for longer sequences |
| No natural language interface | Poor usability |
| No video rendering | Blocks paper figures |

---

## Phase 1: Immediate Wins (1–2 Weeks)

### 1.1 Tracking Quality Metrics Engine ⭐ (Foundation for all learning)

**What:** Add per-step error accumulation inside `track()` → emit metrics in `result.json`.

Metrics to add:
- `maje_deg` — mean absolute joint error (deg) over all DOFs and frames
- `root_height_error_mean` — mean `|actual_z - reference_z|`
- `tracking_success_margin` — minimum root height above 0.20m fall threshold
- `phase_lag_frame` — first frame where MAJE exceeds 0.15 rad

**Files:**
- `low_level_execution/gmt_tracking_runner.py` — accumulate per-step deltas inside `track()`, return in `RunnerTrackResult`
- `middle_architecture/harness_orchestrator.py` — propagate metrics into `ExecutionResult` and `result.json`

**Verify:** `result.json` for each segment contains the 4 new numeric fields after re-running the demo.

---

### 1.2 Velocity-Aware Transition Interpolation

**What:** Replace naive lerp in `reference_ops.interpolate_reference_frames()` with cubic Hermite spline using velocity boundary conditions at both endpoints.

Derive start velocity from `final_state.dof_vel` (already in `RobotState`); derive end velocity from target motion's first two frames. Use SQUAD (spherical cubic) for quaternion rotation instead of plain slerp.

**Files:**
- `middle_architecture/reference_ops.py` — add `hermite_interpolate_reference_frames()`
- `middle_architecture/transition_builder.py` — call new function when `mode == "interpolation"`

**Verify:** dof velocity delta at seam frame should shrink ≥50% for 20-frame transitions.

---

### 1.3 Pose-Based Motion Matcher

**What:** Replace `matcher.py`'s stub (always returns frame 0, score 0.0) with pose-distance scoring over a configurable search window.

**Formula:**
```
D = λq · mean(|dof_pos_actual - dof_pos_ref[frame]|)
  + λroot · quaternion_log_distance(root_quat_actual, root_quat_ref[frame])
  + λv · mean(|dof_vel_actual - dof_vel_ref[frame]|)
```

Search `[default_start_frame, default_start_frame + 30 frames]`. For `walk_forward` using `basic_walk.pkl` (67 seconds of continuous walking), this finds the correct gait cycle phase instead of always starting at frame 0.

**Files:**
- `middle_architecture/matcher.py` — implement scoring loop
- `configs/harness.yaml` — add `matcher: {mode: pose_distance, lambda_q: 1.0, lambda_root: 0.5, lambda_v: 0.2, search_window_frames: 30}`

---

### 1.4 MuJoCo Headless Video Renderer

**What:** Add offscreen video capture using `mujoco.Renderer` (no display required), annotated with segment ID and MAJE, composited into a single demo MP4.

**Files:**
- `low_level_execution/gmt_tracking_runner.py` — add `_setup_renderer()`, `_capture_frame()` using `mujoco.Renderer(model, height=720, width=1280)`
- `middle_architecture/harness_orchestrator.py` — post-run `compose_demo_video()` with title cards between segments

**Activate:** `HUMASKILL_RECORD=1 python scripts/run_harness_sequence.py`

---

## Phase 2: Core Innovations (1–2 Months)

### 2.1 Transition Feasibility Predictor ⭐ Novel contribution

**What:** Lightweight MLP that predicts transition success probability *before* execution. Enables pre-emptive mode switching (interpolation → bridge) and `num_frames` adjustment.

**Model:**
```
Input (54-dim): [dof_pos_delta(23), root_height_delta(1), root_rot_log_delta(3),
                 dof_vel(23), root_lin_vel(3), num_frames_normalized(1)]
Output: success_prob (BCE) + maje_pred (MSE)
Architecture: 54 → 128 → 64 → 2
```

**Data collection:** `scripts/collect_transition_data.py` — run harness with random sequences and varied `num_frames` (10–60); use Phase 1 metrics as labels.

**Integration:** Before each `build_transition()` call in orchestrator, query predictor. If `success_prob < 0.7`, increase `num_frames` by 10 or switch to bridge mode.

**New files:** `middle_architecture/transition_feasibility.py`, `scripts/collect_transition_data.py`, `scripts/train_transition_predictor.py`
**Modify:** `middle_architecture/harness_orchestrator.py`

---

### 2.2 Skill Graph with Learned Edge Weights

**What:** Represent skills as nodes and transitions as directed edges storing empirical `(attempt_count, success_rate, mean_maje, std_maje)`. Accumulated across runs in `outputs/skill_graph.json`.

Two new capabilities:
- **Fallback lookup** — when `(from_skill, to_skill)` is not in `transitions.yaml`, find a 2-hop path via any bridge skill instead of raising `KeyError`
- **Mode selection** — automatically prefer interpolation vs bridge based on historical success rates

**New files:** `middle_architecture/skill_graph.py`
**Modify:** `middle_architecture/harness_orchestrator.py` (update graph after each segment), `middle_architecture/transition_registry.py` (add `get_or_infer()` fallback)

**Verify:** Define a new task with an unregistered transition pair — system finds a valid path via graph instead of crashing.

---

### 2.3 LLM-Driven Natural Language Task Planner

**What:** Claude API integration that converts natural language instructions to `SkillPlan` objects, grounded by the skill graph for validation.

**Two-stage design:**
1. **LLM stage** — Claude receives full `skills.yaml` + available transitions + user instruction → outputs structured JSON. Use Anthropic SDK with **prompt caching** for the skill registry context (static within session).
2. **Validation stage** — `SkillRegistry.validate()` + skill graph reachability check → send errors back to Claude for correction (max 3 retries).

**New files:** `task_plan/llm_planner.py`, `configs/planner.yaml`
**Modify:** `scripts/run_harness_sequence.py` (add `--nl-task "..."` flag), `task_plan/skill_plan.py` (add `SkillPlan.from_llm_response()`)

**Verify:** `python scripts/run_harness_sequence.py --nl-task "walk forward and then do a kick"` produces the same `SkillPlan` as the existing YAML demo.

---

### 2.4 Adaptive Execution with Tracking Monitor

**What:** Mid-execution degradation detection with 3-tier recovery before the hard fall threshold fires.

**Two thresholds inside `track()`:**
- `warning_threshold` (0.15 rad MAJE) — log warning, increase reference smoothing
- `intervention_threshold` (0.25 rad MAJE) — raise `TrackingDegradedException` with current state

**Recovery strategies (ranked by aggressiveness):**
1. **Extend** — increase `num_frames` by 10 and retry transition
2. **Bridge** — switch current transition to bridge mode using `walk_stand.pkl`
3. **Replan** — use skill graph to find alternative path from current state

**New files:** `middle_architecture/recovery_planner.py`, `middle_architecture/tracking_monitor.py`
**Modify:** `low_level_execution/gmt_tracking_runner.py`, `middle_architecture/harness_orchestrator.py`

---

## Phase 3: Transformative Research (3–6 Months)

### 3.1 Motion Retrieval Database (Content-Addressed Motion Library)

**What:** FAISS vector index over all frames of all `.pkl` files (51-dim embedding per frame). Enables any-to-any skill transitions by retrieving the globally closest motion frame to any robot state — replaces the static `MotionMatcher`.

**Embedding per frame:** `[dof_pos(23), root_pos_relative(3), root_euler_roll_pitch(2), dof_vel_normalized(23)]`

Current 8 files × ~200 avg frames = ~4800 frames. Adding new motion files becomes trivial.

**New files:** `middle_architecture/motion_database.py`, `scripts/build_motion_index.py`
**Modify:** `middle_architecture/matcher.py`

---

### 3.2 Motion VAE for Novel Transition Generation

**What:** Conditional VAE trained on sub-clips from all `.pkl` files. Generates novel transitions by interpolating in latent space between skill endpoint encodings — replaces lerp/slerp with learned generative transitions.

**Architecture:** GRU encoder `(T, 51) → (mu, log_var)` in 32-dim latent; GRU decoder with skill-type one-hot conditioning. Training on ~500–1000 overlapping 60-frame windows.

**Integration:** New `transition_builder.build_vae_transition()` callable via `mode: vae_generated` in `transitions.yaml`.

**New files:** `middle_architecture/motion_vae.py`, `scripts/train_motion_vae.py`
**Modify:** `middle_architecture/transition_builder.py`, `configs/transitions.yaml`

---

### 3.3 Domain Randomization Robustness Sweep

**What:** Perturb MuJoCo model parameters (joint damping ±20%, body mass ±10%, friction ±30%, PD stiffness ±15%) across N=20 instances; measure success rate and MAJE distribution to characterize the sim2real gap.

**Target:** >80% success rate at ±15% parameter noise.

**New files:** `low_level_execution/domain_randomizer.py`, `scripts/run_robustness_sweep.py`

---

### 3.4 Human Video → New Skill via Pose Retargeting

**What:** Pipeline: human MP4 → ViTPose 3D skeleton → IK retargeting to G1 joint space → GMT-compatible `.pkl` export → register as new skill.

Eliminates motion capture requirement. Any human video becomes a potential new skill.

**New files:** `scripts/retarget_human_video.py`, `middle_architecture/retargeter.py`

---

## Innovation Rating Summary

| Innovation | Impact | Feasibility | Novelty | Phase |
|---|---|---|---|---|
| 1.1 Tracking Metrics Engine | High | Very High | Low | 1 — **foundational** |
| 1.2 Velocity-Aware Interpolation | Med-High | High | Low | 1 |
| 1.3 Pose-Based Motion Matcher | Medium | High | Moderate | 1 |
| 1.4 MuJoCo Video Renderer | High (demo) | High | None | 1 |
| 2.1 Transition Feasibility Predictor | Very High | Medium | **High** | 2 |
| 2.2 Skill Graph w/ Learned Edges | High | High | **High** | 2 |
| 2.3 LLM Natural Language Planner | High | High | Moderate | 2 |
| 2.4 Adaptive Tracking Monitor | High | Medium | **High** | 2 |
| 3.1 Motion Retrieval Database | Very High | High | Moderate | 3 |
| 3.2 Motion VAE Generation | Transformative | Medium | **High** | 3 |
| 3.3 Domain Randomization Sweep | High | Medium | Moderate | 3 |
| 3.4 Human Video Skill Imitation | Transformative | Low-Med | **High** | 3 |

---

## Dependency Chain

```
Phase 1.1 Metrics Engine
  → 2.1 Feasibility Predictor (needs training labels)
    → 2.2 Skill Graph (uses predictor for edge weights)
      → 3.1 Motion Retrieval (graph for path planning)
  → 2.4 Adaptive Monitor (needs MAJE signal)
  → 3.3 Domain Randomization (needs metrics for reports)

Phase 1 + 2.2 Skill Graph
  → 2.3 LLM Planner (graph for grounding/validation)

Phase 2.1 Feasibility Predictor
  → 3.2 Motion VAE (evaluate generated transitions)

Phase 1.3 Pose Matcher + 3.1 Motion Database
  → 3.4 Human Video Retargeting (evaluate retargeted motions)
```

---

## Recommended Starting Point

**Implement 1.1 (Metrics Engine) first** — ~1 day of work, unblocks everything. The moment you have numeric quality signals per segment, you can simultaneously start building the Feasibility Predictor dataset (2.1) and evaluating the velocity-aware interpolation improvement (1.2) side by side.
