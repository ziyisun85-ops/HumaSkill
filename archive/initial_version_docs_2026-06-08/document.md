# HumaSkill — Change Log

Three modules were improved: **Evaluation** (tracking quality metrics), **Transition** (Hermite interpolation + smoothness metrics), and **Matching** (pose-based entry-frame search). All changes are backward-compatible.

---

## Files Changed

| File | Type | Lines Added |
|---|---|---|
| `middle_architecture/evaluation.py` | **New** | ~120 |
| `scripts/validate_metrics.py` | **New** | ~70 |
| `scripts/validate_hermite.py` | **New** | ~80 |
| `scripts/validate_matcher.py` | **New** | ~65 |
| `middle_architecture/robot_state.py` | Modified | +25 |
| `middle_architecture/reference_ops.py` | Modified | +190 |
| `middle_architecture/matcher.py` | Modified | +86 |
| `middle_architecture/transition_builder.py` | Modified | +121 |
| `middle_architecture/transition_registry.py` | Modified | +2 |
| `middle_architecture/harness_orchestrator.py` | Modified | +109 |
| `low_level_execution/gmt_tracking_runner.py` | Modified | +36 |
| `configs/harness.yaml` | Modified | +9 |
| `configs/transitions.yaml` | Modified | +1 |

---

## Module 1 — Evaluation Layer

### New file: `middle_architecture/evaluation.py`

Provides pure-numpy metric computation. No MuJoCo or torch imports.

**`SegmentMetrics` dataclass** — fields saved into each segment's `result.json`:

| Field | Unit | Formula |
|---|---|---|
| `maje` | rad | `mean(|tracked_dof - ref_dof|)` across all steps and joints |
| `root_height_error` | m | `mean(|tracked_z - ref_z|)` |
| `root_pos_error` | m | `mean(‖tracked_xy - ref_xy‖₂)` — 2D XY only |
| `root_rot_error` | rad | `mean(2·arccos(|q_tracked · q_ref|))` — geodesic quaternion distance |
| `velocity_error` | m/s | `mean(‖tracked_lin_vel - ref_lin_vel‖₂)` |
| `accel_error` | m/s² | Central-difference second derivative of positions at `control_dt = 0.02 s` |
| `success_margin` | m | `min(tracked_z) − 0.20` — negative means the robot crossed the fall threshold |
| `phase_lag_frame` | frames | Best-matching reference frame at segment end minus expected frame index |
| `num_steps` | — | Total control steps recorded |

**`EvaluationBuffer` class** — call `record(...)` once per control step. Internally converts `root_quat_wxyz → xyzw` on receipt (MuJoCo uses wxyz; GMT uses xyzw).

**`compute_segment_metrics(buffer, control_dt, fall_min_height, reference_fps)`** — called after the tracking loop, returns a populated `SegmentMetrics`.

### Modified: `low_level_execution/gmt_tracking_runner.py`

- `RunnerTrackResult` gains `metrics: Optional[SegmentMetrics] = None` (default `None` — backward-compatible).
- New `_sample_reference_at_step(sampler, control_step)` helper samples the reference position, rotation, DOF, and linear velocity at `motion_time = control_step × control_dt`.
- `track()` now instantiates an `EvaluationBuffer` before the loop, calls `buffer.record(...)` after each physics step, and calls `compute_segment_metrics(...)` before returning (on both success and fall paths).

### Modified: `middle_architecture/harness_orchestrator.py`

- `ExecutionResult` gains `metrics: Optional[SegmentMetrics] = None`.
- `_execute_segment` serializes `track_result.metrics` via `dataclasses.asdict` into `result.json` under key `"metrics"`. If `None`, the key is written as `null`.
- `_execute_segment` also extracts `segment.metadata["transition_metrics"]` and writes it to `result.json` under `"transition_metrics"`.
- `_write_summary` now calls the new `_write_metrics_summary` after writing `run_summary.json`.
- New `_write_metrics_summary` writes `summary_metrics.json` alongside `run_summary.json`.

### New output: `outputs/{task_id}/summary_metrics.json`

```json
{
  "task_id": "demo_walk_kick_crouch_stand",
  "total_segments": 8,
  "aggregate_tracking": {
    "mean_maje": 0.038,
    "max_maje": 0.062,
    "mean_root_height_error": 0.015,
    "mean_root_pos_error": 0.083,
    "mean_root_rot_error": 0.122,
    "mean_velocity_error": 0.047,
    "mean_accel_error": 0.329,
    "min_success_margin": 0.412,
    "mean_phase_lag_frame": 1.3,
    "max_phase_lag_frame": 4
  },
  "aggregate_transitions": {
    "mean_seam_vel_delta": 0.09,
    "max_seam_vel_delta": 0.18,
    "mean_auj": 0.645,
    "max_auj": 1.120,
    "mean_peak_jerk": 2.88,
    "hermite_count": 1,
    "linear_count": 3
  },
  "per_segment": [ ... ]
}
```

### Updated `result.json` schema (additions only, existing 14 keys unchanged)

```json
{
  "metrics": {
    "maje": 0.042,
    "root_height_error": 0.018,
    "root_pos_error": 0.091,
    "root_rot_error": 0.134,
    "velocity_error": 0.052,
    "accel_error": 0.381,
    "success_margin": 0.573,
    "phase_lag_frame": 2,
    "num_steps": 499
  },
  "transition_metrics": {
    "seam_vel_delta": 0.12,
    "seam_accel_delta": 0.54,
    "peak_jerk": 3.21,
    "mean_jerk": 1.07,
    "auj": 0.713,
    "interpolation_mode": "hermite",
    "num_frames": 20
  }
}
```

`transition_metrics` is `null` for skill segments; `metrics` is `null` if collection failed.

---

## Module 2 — Transition Layer

### Modified: `middle_architecture/robot_state.py`

Added **`TransitionMetrics` dataclass** (placed here to avoid circular imports — both `reference_ops.py` and `harness_orchestrator.py` import `robot_state`):

```python
@dataclass
class TransitionMetrics:
    seam_vel_delta: float     # ‖vel_end_transition − vel_start_next_skill‖₂  [m/s]
    seam_accel_delta: float   # ‖accel_end − accel_start_next‖₂               [m/s²]
    peak_jerk: float          # max ‖jerk(i)‖₂ over transition frames          [m/s³]
    mean_jerk: float          # mean ‖jerk(i)‖₂                                [m/s³]
    auj: float                # Accumulated Unsigned Jerk = Σ‖jerk‖ · dt       [m/s²]
    interpolation_mode: str   # "linear" or "hermite"
    num_frames: int
```

### Modified: `middle_architecture/reference_ops.py`

Three new functions added (existing functions unchanged):

**`_derive_frame_velocity(motion, frame_idx) → (root_vel, dof_vel)`**
Returns root linear velocity (3,) and DOF velocity (23,) at a given frame index using forward/central/backward finite differences scaled by `fps`.

**`hermite_interpolate_reference_frames(start, start_lin_vel, start_dof_vel, target_frame, target_lin_vel, target_dof_vel, num_frames, fps, start_ang_vel=None, target_ang_vel=None) → ReferenceFrames`**

Cubic Hermite spline interpolation:
- **`root_pos` and `dof_pos`**: True Hermite cubic using basis polynomials `h00, h10, h01, h11`. Tangents `m0 = start_vel × T` and `m1 = target_vel × T` where `T = num_frames / fps`. Guarantees C1 continuity (position and velocity match) at both endpoints.
- **`root_rot`**: Velocity-aware reparameterization of SLERP. When angular velocities are provided, a cubic blend profile `f(α)` is computed such that the rotation speed at the endpoints matches `start_ang_vel` and `target_ang_vel`, then `root_rot(α) = SLERP(q0, q1, f(α))`. Falls back to regular SLERP when rotation angle is < 1e-6 rad.
- **`local_body_pos`**: Linear interpolation (unchanged behaviour).

The original `interpolate_reference_frames()` (linear) is **not modified**.

**`compute_transition_metrics(transition_frames, next_skill_frames, interpolation_mode) → TransitionMetrics`**

All metrics computed from reference frame positions only — no simulation required:
- Velocity: central finite difference `(pos[i+1] − pos[i-1]) / (2·dt)`
- Acceleration: second-order finite difference `(pos[i+1] − 2·pos[i] + pos[i-1]) / dt²`
- Jerk: third-order finite difference `(pos[i+2] − 2·pos[i+1] + 2·pos[i-1] − pos[i-2]) / (2·dt³)`
- Seam metrics compare the last frame of the transition to the first frame of the next skill

### Modified: `middle_architecture/transition_registry.py`

- `TransitionSpec` gains `interpolation_mode: str = "linear"` (default preserves all existing behaviour).
- `TransitionRegistry.from_yaml` reads `interpolation_mode` from each YAML entry, defaulting to `"linear"`.

### Modified: `middle_architecture/transition_builder.py`

New module-level helper **`_derive_angular_velocity_at_frame(motion, frame_idx)`** — computes angular velocity at a motion frame by quaternion-multiplying adjacent frames and converting to axis-angle.

New method **`_build_interp_frames(spec, current_state, target_frame, target_motion, target_frame_idx, num_frames, fps)`** — dispatches between `hermite_interpolate_reference_frames` (when `spec.interpolation_mode == "hermite"`) and `interpolate_reference_frames` (linear, default). Reads `root_lin_vel`, `dof_vel`, and `root_ang_vel` from `current_state` via `getattr` with zero fallbacks.

All three interpolation call sites updated to use `_build_interp_frames`:
- `build_interpolation_transition`
- `build_bridge_transition` (pre-bridge and post-bridge interp segments)
- `build_bridge_body` (pre-bridge interp segment)
- `build_bridge_post`

Each of these now calls `compute_transition_metrics` after building frames and stores the result in `segment.metadata["transition_metrics"]`.

### Modified: `configs/transitions.yaml`

The `kick_leg → crouch_down` transition is set to `interpolation_mode: hermite` as the first live example. The other two transitions remain `"linear"` (by default — no key needed).

---

## Module 3 — Matching Layer

### Modified: `middle_architecture/robot_state.py`

Added **`MatchConfig` dataclass** and **`DEFAULT_SCORE_WEIGHTS`** dict:

```python
DEFAULT_SCORE_WEIGHTS = {
    "dof_pos": 1.0,
    "root_quat": 0.5,
    "velocity": 0.3,
    "root_height": 0.2,
}

@dataclass
class MatchConfig:
    mode: str = "static"              # "static" | "pose_search"
    search_window: int = 60           # frames to search past default_start_frame
    score_weights: Optional[Dict[str, float]] = None  # None → DEFAULT_SCORE_WEIGHTS
```

### Modified: `middle_architecture/matcher.py`

Complete rewrite of `MotionMatcher` (same public interface):

- `__init__(match_config: Optional[MatchConfig] = None)` — stores config, defaults to `MatchConfig()` (static mode).
- `select()` dispatches to `_static_select` or `_pose_search_select` based on `match_config.mode`.
- **`_static_select`** — old behaviour, always returns `default_start_frame`, `score=0.0`, `reason="static_skill_spec_match"`.
- **`_pose_search_select`** — iterates frames `[default_start_frame, default_start_frame + search_window]`, calls `_pose_score` for each, returns the best frame. `end_frame` shifts by `best_frame - default_start_frame` when `default_end_frame` is set.
- **`_pose_score(robot_state, motion, frame_idx, weights) → float`** — weighted sum of four error terms:
  - DOF position error: `mean(|motion.dof_pos[i] − robot_state.dof_pos|)`
  - Root quaternion distance: `2·arccos(|dot(ref_xyzw, tracked_xyzw)|)` (converts `RobotState.root_quat` from wxyz to xyzw internally)
  - Root velocity error: `‖ref_vel − robot_state.root_lin_vel‖₂` (ref vel from finite diff of motion positions)
  - Root height error: `|motion.root_pos[i, 2] − robot_state.root_pos[2]|`

Module-level helper `_local_derive_frame_vel(motion, frame_idx)` provides frame velocity via forward/central/backward diff (self-contained, not imported from `reference_ops` to keep `matcher.py` decoupled).

### Modified: `middle_architecture/harness_orchestrator.py`

`__init__` parses `config["matching"]` (absent → all defaults) and constructs a `MatchConfig`, which is passed to `MotionMatcher(match_config=...)`.

### Modified: `configs/harness.yaml`

New `matching:` section added (currently `mode: static` — no behavioural change until flipped to `pose_search`):

```yaml
matching:
  mode: static              # "static" | "pose_search"
  search_window: 60
  score_weights:
    dof_pos: 1.0
    root_quat: 0.5
    velocity: 0.3
    root_height: 0.2
```

---

## Validation Scripts (no MuJoCo required)

### `scripts/validate_metrics.py`

Builds a synthetic `EvaluationBuffer` (100 steps, sin-wave trajectories with known noise), runs `compute_segment_metrics`, asserts all fields are populated and in range, checks JSON serialisation round-trip. Runs in < 1 s.

### `scripts/validate_hermite.py`

Builds a 40-frame Hermite transition between two known poses with explicit start/end velocities. Asserts:
- Boundary positions match start and end poses (atol 1e-5)
- Velocity at frame 0 matches `start_lin_vel` (atol 0.1 m/s)
- Velocity at frame 39 matches `target_lin_vel` (atol 0.1 m/s)

Then runs `compute_transition_metrics` on both the Hermite and linear outputs and prints a comparison table of seam velocity delta, seam acceleration delta, peak jerk, mean jerk, and AUJ.

### `scripts/validate_matcher.py`

Loads `basic_walk.pkl`, creates a `RobotState` whose DOF exactly matches frame 10, and runs both static and pose-search modes. Asserts static always returns `default_start_frame` with `score=0.0`, and pose-search finds frame 10 with a low score.

---

## Backward Compatibility Notes

- `RunnerTrackResult.metrics` defaults to `None` — all existing code reading `.success`, `.num_frames`, `.failed_reason` is unaffected.
- `TransitionSpec.interpolation_mode` defaults to `"linear"` — the three existing `transitions.yaml` entries (two without the key, one now with `hermite`) all parse correctly.
- `MatchConfig.mode` defaults to `"static"` — `harness.yaml` defaults to `mode: static`, so no matching behaviour changes until explicitly set to `pose_search`.
- `MotionMatcher()` (no args) still works — `MatchConfig()` provides all defaults.
- The original `interpolate_reference_frames()` function in `reference_ops.py` is unmodified.

---

## Module 4 — Transition Stability Fix

### Problem

Motion clips store world-space root positions baked from capture data. When the robot finishes skill A at world position (5, 0, 0.9) but the next skill's clip starts at the world origin (0, 0, 0.9), interpolating between them pulls the reference backward toward (0, 0), causing the robot to appear to walk backward during transitions.

### Root cause analysis

`interpolate_reference_frames` and `hermite_interpolate_reference_frames` both interpolate from `current_state.root_pos` to `target_kinematic_frame.root_pos`. The target frame's XY was the raw clip position (origin), so the reference pulled in the wrong direction.

### Fix

**New function: `reanchor_kinematic_frame(target_frame, current_state) → KinematicFrame`** in `middle_architecture/reference_ops.py`

Aligns the target frame's XY position and yaw to the current robot state, preserving the target's Z height and joint posture:

```
new_pos = [current_x, current_y, target_z]
delta_yaw = current_yaw − target_yaw
new_quat = yaw_rotation(delta_yaw) × target_quat
dof_pos  = target_dof_pos  (unchanged)
```

Called at the top of `TransitionBuilder._build_interp_frames()` before any interpolation is computed, so all three transition modes (interpolation, bridge pre, bridge post) are covered.

### Config changes (`configs/harness.yaml`)

```yaml
reference_contract:
  root_reference_mode: absolute_root   # was: root_relative
  reanchor_skill_clip: true            # was: false
  reanchor_yaw_only: true
```

`reanchor_skill_clip` also re-anchors the first frame of each skill clip to the robot's position at skill entry — not only transitions — so the full sequence stays anchored.

### Files changed

| File | Change |
|---|---|
| `middle_architecture/reference_ops.py` | New `reanchor_kinematic_frame()` function |
| `middle_architecture/transition_builder.py` | Import + call `reanchor_kinematic_frame` at top of `_build_interp_frames` |
| `configs/harness.yaml` | `root_reference_mode`, `reanchor_skill_clip`, `reanchor_yaw_only` |

---

## Module 5 — Split-Screen Viewer

### New file: `low_level_execution/split_viewer.py`

Renders **reference** (left panel) and **tracked** (right panel) robot states side-by-side in a single OpenCV window during execution.

**`SplitScreenViewer`** class:

- `__init__(model, tracked_data, num_dofs, width, height)` — creates two `mujoco.Renderer` instances (one per panel) and a separate `MjData` for the reference pose; both cameras initialised to `distance=3.5, elevation=-15°, azimuth=90°`.
- `update_reference(root_pos, root_rot_xyzw, dof_pos)` — writes the current reference frame into `ref_data.qpos` (converting xyzw→wxyz for MuJoCo) and calls `mj_kinematics`.
- `render()` — renders both cameras offscreen, concatenates the RGB arrays horizontally, overlays "Reference" / "Tracker" labels with `cv2.putText`, and calls `cv2.imshow("HumaSkill", ...)`. Uses `[:, :, ::-1]` to convert RGB→BGR for OpenCV.
- `close()` — destroys OpenCV windows and releases both renderers.

### Modified: `low_level_execution/gmt_tracking_runner.py`

Four targeted edits:

1. `__init__`: `self.viewer = None` → `self.split_viewer = None`
2. `initialize()`: removed `mujoco_viewer.MujocoViewer`; replaced with `SplitScreenViewer(self.model, self.data, num_dofs=self.num_dofs)` when `self.render` is set.
3. `track()` loop: passes reference frame data `(ref_rp, ref_rr, ref_dof)` to `_render_frame`.
4. `_render_frame(ref_rp=None, ref_rr=None, ref_dof=None)`: calls `split_viewer.update_reference(...)` then `split_viewer.render()`.

### Activation

```powershell
conda activate gmt
$env:HUMASKILL_RENDER = "1"
python scripts/run_harness_sequence.py
```

---

## Module 6 — Hermite Tension Control

### Problem

The kick→crouch hermite transition measured `peak_jerk = 22.7 m/s³` (≈ 3× the mean of other transitions). Root cause: the robot's root velocity after a kick is large; `hermite_interpolate_reference_frames` multiplies it by `T = num_frames / fps` to form the spline tangent `m0 = v_start × T`. A large `m0` causes the cubic to overshoot and snap back, producing high jerk at the endpoints.

### Fix

**New `tension` parameter** in `hermite_interpolate_reference_frames` (default `1.0`):

```python
m0_pos = start_lin_vel * T * tension    # was: * T
m1_pos = target_lin_vel * T * tension
m0_dof = start_dof_vel * T * tension
m1_dof = target_dof_vel * T * tension
# rotation alpha derivatives scaled the same way
m0_alpha = d0_rot * tension
m1_alpha = d1_rot * tension
```

Endpoint positions and DOF are always exactly matched regardless of tension (the `h00`/`h01` basis terms are unchanged). Only the tangent magnitude is scaled. Setting `tension = 0.5` halves all tangents, reducing overshoot and therefore peak jerk, while `tension = 1.0` reproduces the original behaviour exactly.

**Validation** (`scripts/validate_hermite.py`): with a large start velocity of `[3.0, 0.5, 0.0] m/s` (post-kick scenario), `tension=0.5` reduces `peak_jerk` from `5.55` to `1.84` while endpoints remain within `atol=1e-5`.

### New `hermite_tension` field in `TransitionSpec`

```python
@dataclass
class TransitionSpec:
    ...
    hermite_tension: float = 1.0   # default — no behavioural change
```

Parsed from `transitions.yaml` via `float(raw.get("hermite_tension", 1.0))`.

### Updated `configs/transitions.yaml`

| Transition | Mode | tension | Reason |
|---|---|---|---|
| kick→crouch | hermite | 0.5 | Large post-kick velocity; halving tangents reduces peak jerk |
| crouch→stand | hermite | 0.8 | Upgraded from linear; modest exit velocity, gentle damping |
| walk→kick | bridge | — | Bridge mode; no hermite interpolation in main body |

### Files changed

| File | Change |
|---|---|
| `middle_architecture/reference_ops.py` | `tension` parameter in `hermite_interpolate_reference_frames` |
| `middle_architecture/transition_registry.py` | `hermite_tension: float = 1.0` in `TransitionSpec`; parsed in `from_yaml` |
| `middle_architecture/transition_builder.py` | `tension=spec.hermite_tension` passed to `hermite_interpolate_reference_frames` |
| `configs/transitions.yaml` | `hermite_tension: 0.5` on kick→crouch; hermite + `hermite_tension: 0.8` on crouch→stand |
| `scripts/validate_hermite.py` | Tension assertion with high-velocity test case |

### Backward compatibility

- `tension` defaults to `1.0` — all existing callers of `hermite_interpolate_reference_frames` are unaffected.
- `hermite_tension` defaults to `1.0` in `TransitionSpec` — existing YAML entries without the key parse identically to before.
