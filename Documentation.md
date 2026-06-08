# Documentation — HumaSkill Living Project Record

> This document is updated continuously. After each milestone completes, update status, record key decisions, and capture the latest validation results. See `Prompt.md` for improvement objectives and `Plan.md` for the current milestone roadmap.

---

## Current State (Improvement Phase)

**Phase:** Post-v1 improvement pass completed. M1 transition jerk reduction, M2 bridge post-interp fix, M3 pose-search calibration, and M4 final validation sweep are applied and validated.

**Pipeline:** `walk_forward (10s) → [bridge] → kick_leg → [hermite] → crouch_down → [hermite] → stand_up`

**Last full run:** 2026-06-08. All 8 segments succeeded with `pose_search` enabled, transition-to-skill future-reference lookahead active, and no fall detection trigger. Latest metrics below.

### Baseline Metrics (Pre-Improvement)

| Metric | Value | Target |
|--------|-------|--------|
| Mean MAJE | 0.0625 | maintain |
| Mean seam velocity delta | 0.110 m/s | ≤ 0.10 |
| transition_002 peak jerk | **22.7** | < 5.0 |
| transition_002 AUJ | **6.03** | < 2.0 |
| skill_003 success margin | **0.284** | > 0.25 |
| Min success margin (all) | 0.284 | > 0.25 |

### Latest Metrics (Post-M4 + Future Lookahead)

| Metric | Value | Target |
|--------|-------|--------|
| Mean MAJE | 0.0666 | maintain |
| Mean seam velocity delta | 0.0274 m/s | <= 0.10 |
| transition_002 peak jerk | **3.569** | < 5.0 |
| transition_002 AUJ | **1.178** | < 2.0 |
| skill_003 success margin | **0.2817** | > 0.25 |
| Min success margin (all) | 0.2817 | > 0.25 |

### Improvement Milestone Status

| Milestone | Status | Notes |
|-----------|--------|-------|
| M1 — Fix transition_002 hermite jerk | ✅ Completed | `transition_002` now uses Hermite tension `0.1` over 24 frames; peak jerk 2.983, AUJ 0.979 |
| M2 — Bridge post-interp real state | ✅ Completed | Bridge post starts from real runner state and uses velocity-aware Hermite; seam velocity 0.023 |
| M3 — Calibrate pose_search matching | ✅ Completed | Global `pose_search` enabled; active weights validated; crouch margin remains > 0.25 |
| M4 — Full pipeline re-run | ✅ Completed | All Prompt.md done-when criteria met on final run |

### M1 Validation Results (2026-06-08)

Changed `configs/transitions.yaml` for `kick_leg -> crouch_down`: kept Hermite interpolation, lowered `hermite_tension` to `0.1`, and increased `num_frames` from 20 to 24. Propagation through `TransitionRegistry` and `TransitionBuilder._build_interp_frames()` was inspected and already correct; no code change was needed for routing.

Decision: tension tuning alone reduced AUJ but could not reliably bring peak jerk under target at 20 frames. A no-edit diagnostic showed root velocity tangents were modest, while the 20-frame cubic duration still had a minimum peak jerk above target. The scoped fix was to lengthen only `transition_002` to 24 frames.

Validation commands:

```text
conda activate gmt; python scripts/validate_hermite.py
-> exit 0; Hermite boundary and C1 continuity checks passed.

conda activate gmt; python scripts/run_harness_sequence.py --config configs/harness.yaml --sequence configs/sequences/demo_walk_kick_crouch_stand.yaml --skills configs/skills.yaml --transitions configs/transitions.yaml
-> exit 0; all 8 segments reported success=True.
```

Fresh `outputs/demo_walk_kick_crouch_stand/transition_002_kick_leg_to_crouch_down/result.json`:

| Metric | Target | Actual |
|--------|--------|--------|
| peak_jerk | < 5.0 | 2.983 |
| AUJ | < 2.0 | 0.979 |
| seam_vel_delta | <= 0.10 | 0.0068 |

### M2 Validation Results (2026-06-08)

Inspected `middle_architecture/harness_orchestrator.py`, `middle_architecture/transition_builder.py`, and `low_level_execution/gmt_tracking_runner.py`. The bridge-body call site already carried `body_result.final_state` into `build_bridge_post()`, and `GMTTrackingRunner.get_robot_state()` already populated `root_lin_vel`, `root_ang_vel`, and `dof_vel`.

Decision: the remaining bridge-post seam velocity came from linear post interpolation discarding the real runner velocity and failing to match the kick entry velocity. `build_bridge_post()` now uses velocity-aware Hermite with tension `1.0` when the bridge exit state is a real state with velocity fields; bridge body and configured interpolation transitions keep their existing behavior.

Validation commands:

```text
conda activate gmt; python scripts/run_harness_sequence.py --config configs/harness.yaml --sequence configs/sequences/demo_walk_kick_crouch_stand.yaml --skills configs/skills.yaml --transitions configs/transitions.yaml
-> exit 0; all 8 segments reported success=True.

conda activate gmt; python -m py_compile middle_architecture/transition_builder.py middle_architecture/harness_orchestrator.py low_level_execution/gmt_tracking_runner.py
-> exit 0.
```

Fresh `outputs/demo_walk_kick_crouch_stand/transition_001_walk_forward_to_kick_leg_post/result.json`:

| Metric | Target | Actual |
|--------|--------|--------|
| seam_vel_delta | <= 0.10 | 0.0231 |
| first post frame vs. runner bridge-exit root_pos | <= 0.01 m | 0.0 m in diagnostic |
| segment success | true | true |

### M3 Validation Results (2026-06-08)

Changed `configs/harness.yaml` to enable global `pose_search` and updated score weights to emphasize crouch height:

```yaml
matching:
  mode: pose_search
  search_window: 60
  score_weights:
    dof_pos: 1.0
    root_quat: 0.3
    velocity: 0.2
    root_height: 0.8
```

Updated `scripts/validate_matcher.py` to load the active harness weights and assert that a known-good frame scores below a frame at least 10 frames away.

Validation commands:

```text
conda activate gmt; python scripts/validate_matcher.py
-> exit 0; pose_search selected frame 10; score frame 10 = 0.151137, frame 25 = 0.351137.

conda activate gmt; python scripts/run_harness_sequence.py --config configs/harness.yaml --sequence configs/sequences/demo_walk_kick_crouch_stand.yaml --skills configs/skills.yaml --transitions configs/transitions.yaml
-> exit 0; all 8 segments reported success=True.
```

Fresh runtime observations:

| Metric | Baseline | Actual |
|--------|----------|--------|
| `skill_003_crouch_down` success_margin | 0.284 | 0.2817 |
| `skill_001_walk_forward` success_margin | 0.571 | 0.5675 |
| min success_margin | > 0.25 target | 0.2817 |

Decision: global `pose_search` is acceptable for now because it introduced no falls, kept `walk_forward` above the 0.45 regression threshold from `Implement.md`, and kept all margins above the Prompt target. The crouch margin did not improve in this run, so this remains a calibration area rather than a confirmed quality gain.

### M4 Final Validation Results (2026-06-08)

Validation commands:

```text
conda activate gmt; python scripts/validate_hermite.py
-> exit 0.

conda activate gmt; python scripts/validate_matcher.py
-> exit 0.

conda activate gmt; python scripts/validate_metrics.py
-> exit 0.

conda activate gmt; python scripts/run_harness_sequence.py --config configs/harness.yaml --sequence configs/sequences/demo_walk_kick_crouch_stand.yaml --skills configs/skills.yaml --transitions configs/transitions.yaml
-> exit 0; all 8 segments reported success=True.
```

Final done-when check from `outputs/demo_walk_kick_crouch_stand/summary_metrics.json`:

| Criterion | Target | Actual |
|-----------|--------|--------|
| Full pipeline success | true | true |
| `transition_002` peak_jerk | < 5.0 | 2.768 |
| `transition_002` AUJ | < 2.0 | 0.907 |
| Mean seam_vel_delta | <= 0.10 | 0.0227 |
| Min success_margin | > 0.25 | 0.2817 |
| All segment success flags | true | true |

### Transition Orientation Fix (2026-06-08)

Follow-up investigation found two continuity issues around action seams:

1. Bridge body reference frames were appended in raw pkl coordinates after a reanchored pre-interp segment. This caused a synthetic test offset by yaw/XY to produce a `5.385m` XY jump and `109.58deg` yaw jump at the pre->bridge seam.
2. The next skill clip was matched and reanchored before executing the transition. In the real sequence, `walk_forward -> kick_leg` produced a post-transition yaw mismatch of about `124deg` and an XY mismatch of about `3.10m` against the next skill's first reference frame.

Fixes:

- `TransitionBuilder.build_bridge_body()` and the combined bridge path now reanchor the full bridge motion slice to the same root/yaw target used by the pre-interp endpoint.
- `HarnessOrchestrator.execute()` now performs skill matching, slicing, and `reanchor_reference_frames()` after the transition has executed, so the next skill starts from the latest real `RobotState`.
- `walk_forward -> kick_leg` `post_bridge_interp_frames` was increased from 15 to 24 to keep bridge-post jerk low after the coordinate/yaw fix.

New validation commands:

```text
conda activate gmt; python scripts/validate_transition_alignment.py
-> exit 0; bridge body xy_jump=0.0m, yaw_jump=0.0deg.

conda activate gmt; python scripts/validate_orchestrator_reanchor_timing.py
-> exit 0; second skill first root is reanchored to the post-transition state.
```

Full validation after the fix:

```text
conda activate gmt; python scripts/validate_transition_alignment.py
conda activate gmt; python scripts/validate_orchestrator_reanchor_timing.py
conda activate gmt; python scripts/validate_hermite.py
conda activate gmt; python scripts/validate_matcher.py
conda activate gmt; python scripts/validate_metrics.py
conda activate gmt; python scripts/run_harness_sequence.py --config configs/harness.yaml --sequence configs/sequences/demo_walk_kick_crouch_stand.yaml --skills configs/skills.yaml --transitions configs/transitions.yaml
-> all exited 0; all 8 runtime segments reported success=True.
```

Fresh post-fix observations:

| Metric | Before orientation fix | After orientation fix |
|--------|------------------------|-----------------------|
| `walk_forward -> kick_leg` skill-start yaw mismatch | 123.95deg | 0.0deg |
| `walk_forward -> kick_leg` skill-start XY mismatch | 3.10m | 0.0m |
| Mean root position error | 0.696 | 0.170 |
| Mean root rotation error | 0.482 | 0.163 |
| `transition_001_post` peak jerk | 8.90 before post-frame retune | 2.816 |
| `transition_001_post` AUJ | 3.27 before post-frame retune | 1.878 |
| Mean seam_vel_delta | 0.0227 | 0.0178 |

### Transition Call Chain Cleanup (2026-06-08)

Current action-switching code path is intentionally limited to one orchestrator path:

1. `HarnessOrchestrator.execute()` reads the live `RobotState`.
2. `MotionMatcher.select()` chooses the next skill clip start frame. With current config this is `pose_search`.
3. If this is not the first skill, `TransitionRegistry.get(previous_skill, current_skill)` loads the configured transition spec.
4. For `mode: bridge`, the orchestrator executes:
   - `TransitionBuilder.build_bridge_body()` for pre-interp + reanchored bridge motion.
   - `TransitionBuilder.build_bridge_post(..., target_frame_idx=match.start_frame)` for Hermite post-interp into the same frame that the next skill will use.
5. For `mode: interpolation`, the orchestrator executes:
   - `TransitionBuilder.build_transition(..., target_frame_idx=match.start_frame)`.
6. The next skill reference is sliced from the same `match.start_frame`, then reanchored to the latest post-transition `RobotState`, and finally sent to `GMTTrackingRunner.track()`.

Cleanup:

- Removed unused `TransitionBuilder.build_bridge_transition()`. The actual runtime bridge path is split into body + post so the post segment can start from the real runner state.
- Removed unused `_frame_from_reference_frames()`.
- Removed unused `next_skill_spec` argument from `build_bridge_body()`.
- Added `scripts/validate_transition_target_match_consistency.py` to prevent regression where transition targets default frame 0 but pose_search starts the next skill from a different frame.

Fresh validation after cleanup:

```text
conda activate gmt; python scripts/validate_transition_alignment.py
conda activate gmt; python scripts/validate_orchestrator_reanchor_timing.py
conda activate gmt; python scripts/validate_transition_target_match_consistency.py
conda activate gmt; python scripts/validate_hermite.py
conda activate gmt; python scripts/validate_matcher.py
conda activate gmt; python scripts/validate_metrics.py
conda activate gmt; python scripts/run_harness_sequence.py --config configs/harness.yaml --sequence configs/sequences/demo_walk_kick_crouch_stand.yaml --skills configs/skills.yaml --transitions configs/transitions.yaml
-> all exited 0; all 8 runtime segments reported success=True.
```

Matched-frame seam diagnostic after cleanup:

| Seam | matched start | DOF mean jump | DOF max jump |
|------|---------------|---------------|--------------|
| `walk_forward -> kick_leg` | 14 | 0.0000 | 0.0000 |
| `kick_leg -> crouch_down` | 60 | 0.0000 | 0.0000 |
| `crouch_down -> stand_up` | 9 | 0.0000 | 0.0000 |

### Future Reference Window Lookahead (2026-06-08)

Follow-up change for remaining visual non-smoothness at action boundaries:

- `GMTTrackingRunner.track()` now accepts optional `future_reference_frames`.
- `_get_mimic_obs()` samples future target times from the current segment until the current segment ends; target times beyond the segment duration are stitched into the supplied future segment instead of wrapping back to the current segment start.
- `HarnessOrchestrator` passes the next skill's expected, reanchored reference frames as lookahead when executing interpolation transitions and bridge post transitions.
- Normal skill calls and any runner call without `future_reference_frames` keep the old behavior.
- No action smoothing was added. The first fix targets the policy input discontinuity directly instead of filtering policy outputs.

New validation:

```text
conda activate gmt; python scripts/validate_future_reference_window.py
-> exit 0; future window crosses segment boundary without wrapping.

conda activate gmt; python scripts/validate_transition_target_match_consistency.py
-> exit 0; transition endpoint, transition lookahead first frame, and following skill first frame match.
```

Full validation after lookahead:

```text
conda activate gmt; python -m py_compile low_level_execution/gmt_tracking_runner.py middle_architecture/harness_orchestrator.py scripts/validate_future_reference_window.py scripts/validate_transition_target_match_consistency.py scripts/validate_orchestrator_reanchor_timing.py
conda activate gmt; python scripts/validate_future_reference_window.py
conda activate gmt; python scripts/validate_transition_alignment.py
conda activate gmt; python scripts/validate_orchestrator_reanchor_timing.py
conda activate gmt; python scripts/validate_transition_target_match_consistency.py
conda activate gmt; python scripts/validate_hermite.py
conda activate gmt; python scripts/validate_matcher.py
conda activate gmt; python scripts/validate_metrics.py
conda activate gmt; python scripts/run_harness_sequence.py --config configs/harness.yaml --sequence configs/sequences/demo_walk_kick_crouch_stand.yaml --skills configs/skills.yaml --transitions configs/transitions.yaml
-> all exited 0; all 8 runtime segments reported success=True.
```

Fresh lookahead metrics from `outputs/demo_walk_kick_crouch_stand/summary_metrics.json`:

| Metric | Value |
|--------|-------|
| Mean MAJE | 0.0666 |
| Mean root position error | 0.1713 |
| Mean root rotation error | 0.1549 |
| Mean seam velocity delta | 0.0274 |
| Max seam velocity delta | 0.0368 |
| Mean AUJ | 1.2954 |
| Max AUJ | 1.5832 |
| Min success margin | 0.2817 |

Remaining boundary limitation: bridge body still cannot receive bridge-post lookahead because bridge post is intentionally built only after the bridge body runs and the real robot state is known. The transition/post-to-skill boundary now has future-reference continuity; the body-to-post boundary remains governed by real-state Hermite post interpolation.

---

## How to Run

### Environment Setup

```bash
conda activate gmt
cd G:\Code\Python\HumaSkill
```

### Full Pipeline

```bash
python scripts/run_harness_sequence.py \
  --config configs/harness.yaml \
  --sequence configs/sequences/demo_walk_kick_crouch_stand.yaml \
  --skills configs/skills.yaml \
  --transitions configs/transitions.yaml
```

Output: `outputs/demo_walk_kick_crouch_stand/`

### Unit Validation Scripts

```bash
python scripts/validate_hermite.py     # Hermite boundary conditions and C1 continuity
python scripts/validate_matcher.py     # Static and pose_search frame selection
python scripts/validate_metrics.py     # Segment metrics computation
```

### Single Motion Test

```bash
python scripts/run_single_gmt_motion.py --motion walk_stand.pkl --duration 5.0
```

---

## Open Questions (Post-Improvement)

1. **Can pose_search improve crouch margin rather than only preserve it?** M3 enabled global pose_search and kept `skill_003_crouch_down` above target, but the margin remains close to baseline at 0.2838. Further calibration may need per-skill windows or scoring terms.
2. **What is the right warning threshold for `success_margin`?** Current floor is 0.25; crouch_down remains marginal at 0.2838. Consider logging a warning at 0.30.

---

## Known Issues (Improvement Phase)

| ID | Issue | Severity | Improvement Milestone |
|----|-------|----------|-----------------------|
| P1 | Resolved in M1: `transition_002` peak_jerk reduced to 2.983 with Hermite tension 0.1 over 24 frames | High | M1 |
| P2 | Resolved in M2: bridge post starts from real runner state and preserves velocity continuity with Hermite post interpolation | Medium | M2 |
| P3 | Resolved for M3 acceptance: `pose_search` enabled globally and score ordering validated; crouch margin stayed above target but did not improve | Low-Med | M3 |
| P4 | Resolved: bridge body and next-skill clips now reanchor with post-transition root position/yaw, eliminating observed action seam yaw/XY mismatch | High | Orientation fix |
| P5 | Resolved for transition/post-to-skill seams: runner future-reference window now stitches into the next skill instead of wrapping to the current segment start; action smoothing was not added | Medium | Future lookahead |

---

## v1 Delivery Record (Historical)

> Original Chinese milestone log preserved below. v1 delivered on 2026-06-03; all M0–M5 milestones completed.

---

## 当前状态

| Milestone | 状态 | 完成日期 | 备注 |
|-----------|------|---------|------|
| P0 (GMT 环境验证) | ⬜ 待人工执行 | — | Codex 未运行 60s viewer 命令；当前 GMT 资产和依赖已在 M0 中静态核验 |
| M0 (obs/reference 契约) | ✅ completed | 2026-06-03 | `outputs/contract/GMT_obs_reference_contract.md` 已生成并通过 validation |
| M1 (GMTTrackingRunner) | ✅ completed | 2026-06-03 | single-motion smoke、RobotState、连续 track validation 均通过 |
| M2 (Task Plan 层) | ✅ completed | 2026-06-03 | SkillPlan parse 和 SkillRegistry validation 均通过 |
| M3a (motion adapter + ref_ops) | ✅ completed | 2026-06-03 | motion load/slice/interpolate/concat validation 通过 |
| M3b (transition registry + builder) | ✅ completed | 2026-06-03 | registry、missing transition、builder constructor、transition shape validation 通过 |
| M3c (matcher) | ✅ completed | 2026-06-03 | walk_forward duration=10s -> 300 frames |
| M3d (root 重锚) | ✅ completed | 2026-06-03 | pass-through 与 absolute-root yaw+translation 分支均可调用；默认按 M0 不重锚 |
| M4 (端到端集成) | ✅ completed | 2026-06-03 | 单 episode 7 段端到端运行全部 success |
| M5 (产物收敛) | ✅ completed | 2026-06-03 | 最终全量核验通过 |

**当前阶段**：第一版交付完成。

---

## 关键决策及理由

### 决策 1：执行模型 — 常驻单 episode + import runner

**内容**：在同一个 MuJoCo episode 中，使用可 import 的 `GMTTrackingRunner` 连续执行多段 reference frames。段间不 reset 物理状态。不逐段 subprocess 调 `sim2sim.py`。

**理由**：

- 只有物理状态连续不 reset，过渡段（transition）才有意义——transition 需要从"上一段真实结束状态"出发。
- 逐段 subprocess 意味着每段新启一个 MuJoCo episode，物理状态不连续，transition 就成了无源之水。
- import runner 也让状态的传递和摔倒检测更直观。

---

### 决策 2：Transition = 可被同一 policy 追踪的 reference 轨迹

**内容**：transition 本身是一条 reference 轨迹，不是特殊的控制模式。它由 `interpolation`（在线 lerp/slerp）或 `bridge`（pre + pkl 片段 + post）生成 reference_frames，然后交给同一个 tracking policy 执行。

**理由**：

- 复用 GMT 已有的 tracking policy，不用训练专门的 transition policy。
- transition 的 reference frames 与 skill 的 reference frames 是同一数据结构（`ReferenceFrames`），底层 `track()` 不需要区分。
- bridge 模式使用真实 GMT pkl 片段（`walk_stand.pkl` / `crouchwalk_stand.pkl`），保证过渡段的运动学合理。

---

### 决策 3：Root 重锚策略 — 条件分支，M0 后选定

**内容**：不二选一写死。两种分支都实现：

- **分支 A**（obs 使用 absolute root）：skill clip 和 transition target entry 都需要重锚到当前真实 root。
- **分支 B**（obs 使用 root relative 或速度量）：skill clip 保持相对参考，不重锚（或仅 yaw 重锚）。

**M0 结论**：GMT policy 不直接观察完整 absolute root 的 x/y/yaw reference；它观察 reference root height z、roll/pitch、局部 root linear velocity、局部 yaw angular velocity 和 dof_pos。因此第一版按 `root_relative` 分支执行，`reanchor_skill_clip=false`。细化事实是：global x/y/yaw 不作为 tracking target，但 root height z 仍是 reference target。两种分支仍需在代码中保留。

**理由**：`sim2sim.py` 的 `_get_mimic_obs()` 只拼接 `root_pos[..., 2:3]`、roll/pitch、local root velocity、local yaw angular velocity 和 `dof_pos`；不拼接 root x/y/yaw。

---

### 决策 4：摔倒判定 — 最小阈值，先占位后调整

**内容**：root 高度过低或机身倾角过大 → `success=False, failed_reason="fell"`。GMT 原始 `sim2sim.py` 没有 runtime fall detection；阈值属于 harness 经验配置，M1 先放入 `configs/harness.yaml` 并由 smoke test 继续校准。

**理由**：

- 最小摔倒判定是第一版的底线安全网。没有它，机器人跌倒后还在"跑成功"，结果无意义。
- 阈值不能编造——仰角多少算"倒"需要实际跑一次看正常范围。

**占位配置**（`configs/harness.yaml`）：

```yaml
fall_detection:
  enabled: true
  min_root_height: pending_m0_or_empirical_config
  max_body_tilt: pending_m0_or_empirical_config
```

---

### 决策 5：kick_leg 用 airkick_stand.pkl

**内容**：第一版 `kick_leg` 使用 `airkick_stand.pkl`。

**理由**：任务链路中 `walk_forward → kick_leg` 已经设计了 `stable_stand_bridge` 过渡，即先 bridge 到稳定站立再踢腿，因此空中站立踢腿（`airkick_stand.pkl`）比边走边踢（`kick_walk.pkl`）更匹配。`kick_walk.pkl` 保留为后续可选对比项。

---

### 决策 6：crouch_down 用 squat.pkl

**内容**：第一版 `crouch_down` 使用 `squat.pkl`。

**理由**：任务语义是"蹲下"，`squat.pkl`（深蹲）比 `crouchwalk_stand.pkl`（蹲走）语义更直接。`crouchwalk_stand.pkl` 保留给 bridge 或后续对比。若 tracking 效果差，可从 `crouchwalk_stand.pkl` 中截取更稳定的蹲姿片段替换。

---

### 决策 7：device 优先 CPU，再切 GPU

**内容**：使用 `auto` 策略。M0 中 `gmt` 环境检测结果为 `torch.cuda.is_available() == False`，当前实际设备为 CPU。

**理由**：第一版核心风险在 runner 重构和 obs 契约，CPU 足以验证逻辑正确性。先在 CPU 上消除 runner 层面的 bug，减少 CUDA 相关变量。

---

### 决策 8：视频不作为硬性交付物

**内容**：第一版不把视频录制列为必须交付。等主链路跑通后，可录一个 demo 视频作为展示材料。

**理由**：验收先看 runner 连续执行、RobotState 回传、transition 生成和摔倒返回。这些通过代码核验和日志确认。视频是锦上添花，不是通关条件。

---

## 如何运行

### 环境要求

- Python 3.8+
- MuJoCo（版本与 GMT 兼容）
- GMT 仓库已 clone 且可独立运行 `sim2sim.py`
- 8 个 GMT `.pkl` motion 文件存在于 `assets/motions/`

### GMT 路径配置

`configs/harness.yaml` 中设置：

```yaml
gmt:
  root: G:/Code/Python/Paper-Reproduction/GMT/humanoid-general-motion-tracking
  robot: g1
  device: auto
```

`device` 可选值：`auto`、`cpu`、`cuda`。

### 前置步骤

```bash
# P0：确认 GMT 原始环境可用
cd G:/Code/Python/Paper-Reproduction/GMT/humanoid-general-motion-tracking
python sim2sim.py --robot g1 --motion walk_stand.pkl
```

### 运行第一版任务

```bash
# 端到端执行固定序列
cd G:\Code\Python\HumaSkill
python scripts/run_harness_sequence.py
```

### 单 motion 测试

```bash
python scripts/run_single_gmt_motion.py --motion walk_stand.pkl --duration 5.0
```

### 查看 pkl 格式

```bash
python scripts/inspect_gmt_motion_format.py assets/motions/walk_stand.pkl
```

### 运行 M0 契约调查

```bash
python scripts/inspect_gmt_obs_reference_contract.py ^
  --gmt-root G:/Code/Python/Paper-Reproduction/GMT/humanoid-general-motion-tracking ^
  --sim2sim sim2sim.py ^
  --output outputs/contract/GMT_obs_reference_contract.md
```

---

## M0 契约摘要

**GMT 路径来源**：按查找顺序未发现 `GMT_ROOT` 环境变量；采用文档默认路径 `G:/Code/Python/Paper-Reproduction/GMT/humanoid-general-motion-tracking`，该路径存在且包含 `sim2sim.py`、8 个 motion pkl、`assets/pretrained_checkpoints/pretrained.pt` 和 `assets/robots/g1/g1.xml`。

**设备选择**：`gmt` conda 环境存在，Python 3.8.20；Torch 为 CPU build，CUDA 不可用，因此 `device=auto` 实际选择 CPU。

**核心数值**：physics dt = `0.001s`，物理频率 1000Hz；decimation = `20`；control dt = `0.02s`，控制频率 50Hz；history window = 20 个 proprio frames；obs 无外部 mean/std normalizer，仅使用 `ang_vel_scale=0.25`、`dof_pos_scale=1.0`、`dof_vel_scale=0.05`。

**reference 时间索引**：控制步使用 segment-local control time；`tar_obs_steps=[1,5,10,...,95]`，即向未来看 0.02s 到 1.90s；MotionLib 使用 `(N-1)/fps` 作为 motion length，按 phase 找 `frame_idx0/frame_idx1/blend`，root/dof 线性插值，root rot slerp，并对 motion time 做 loop。

**obs/reference 结构**：mimic obs 为 20 个未来 reference 点，每点包含 root z、roll、pitch、local root velocity、local yaw angular velocity、dof_pos；proprio obs 包含当前 ang_vel、roll/pitch、dof_pos offset、dof_vel、last_action；history 只保存 proprio obs。

**motion 契约**：pkl 字段包含 `fps/root_pos/root_rot/dof_pos/local_body_pos/link_body_list`；`root_pos=(N,3)`，`root_rot=(N,4)`，`dof_pos=(N,23)`，`local_body_pos=(N,38,3)`。GMT 源码事实显示 motion `root_rot` 为 `xyzw`，写入 MuJoCo `qpos[3:7]` 时转换为 `wxyz`。这与 `Architecture_Desgin.md` 中 “wxyz” 描述冲突，按 M0 源码事实执行并记录。

**local_body_pos**：motion adapter 需要读取并保留，但 GMT runner obs 不消费。

**reference velocity**：pkl 不含速度；`MotionLib` 从 reference 差分派生 root/root angular/dof velocity，并用窗口 19 smoothing。

**Validation 结果**：

```text
G:\App\Miniconda\envs\gmt\python.exe scripts/inspect_gmt_obs_reference_contract.py --gmt-root G:/Code/Python/Paper-Reproduction/GMT/humanoid-general-motion-tracking --sim2sim sim2sim.py --output outputs/contract/GMT_obs_reference_contract.md
-> Wrote M0 contract: outputs\contract\GMT_obs_reference_contract.md (16394 bytes)

G:\App\Miniconda\envs\gmt\python.exe -c "... size check ..."
-> M0 contract OK: 16394 bytes

G:\App\Miniconda\envs\gmt\python.exe -c "... keyword check ..."
-> found 22 keywords; missing []
```

**M0 修改文件**：

```text
scripts/inspect_gmt_obs_reference_contract.py
outputs/contract/GMT_obs_reference_contract.md
Documentation.md
```

**已知风险**：Plan.md 的 P0 示例使用 `--motion`，当前 GMT `sim2sim.py --help` 实际参数为 `--motion_file`；后续 harness 脚本可以使用自己的 `--motion` 参数，但直接调用原版 GMT 时必须使用 `--motion_file`。

---

## M1 GMTTrackingRunner 记录

**范围**：实现可 import 的 `GMTTrackingRunner`，按 M0 结论复刻 GMT `sim2sim.py` 的核心控制循环；为 M1 validation 所需，提前创建了架构已列出的 `middle_architecture/robot_state.py`、`middle_architecture/gmt_motion_adapter.py`、`middle_architecture/reference_ops.py` 的基础能力，以及 `scripts/run_single_gmt_motion.py` 和 `configs/harness.yaml`。

**文档冲突处理**：Implement.md 的 milestone 白名单把 `run_single_gmt_motion.py` 放在 M4、adapter/reference_ops 放在 M3，但 Plan.md 的 M1 validation commands 会直接运行 `scripts/run_single_gmt_motion.py` 并 import `middle_architecture.gmt_motion_adapter` / `reference_ops`。按用户给定优先级，Plan.md 高于 Implement.md，因此为通过 M1 validation 提前创建这些架构内文件；未创建架构外模块。

**关键实现决策**：

- `initialize()` 只加载一次 MuJoCo model/data 和 TorchScript policy；`track()` 不调用 reset。
- 不创建 viewer，避免 smoke test 依赖 Windows 图形窗口；physics/policy 逻辑仍按 M0 契约执行。
- `track()` 内部使用 segment-local reference time，按 `(N-1)/fps`、loop、phase、blend、linear/slerp 采样 reference。
- `last_action` 和 20 帧 proprio history 跨 `track()` 保留。
- `RobotState.root_quat` 来自 MuJoCo `qpos[3:7]`，顺序为 `wxyz`；`ReferenceFrames.root_rot` 保持 GMT pkl `xyzw`。
- fall detection 是 harness 经验配置：`min_root_height=0.20`，`max_body_tilt=120.0`；GMT 原始 sim2sim 无阈值。

**修改文件**：

```text
configs/harness.yaml
assets/motions/*.pkl
low_level_execution/gmt_tracking_runner.py
middle_architecture/robot_state.py
middle_architecture/gmt_motion_adapter.py
middle_architecture/reference_ops.py
scripts/run_single_gmt_motion.py
Documentation.md
```

**Validation 结果**：

```text
G:\App\Miniconda\envs\gmt\python.exe -m py_compile ...
-> exit 0

G:\App\Miniconda\envs\gmt\python.exe scripts/run_single_gmt_motion.py --motion walk_stand.pkl --duration 3.0
-> single motion result: success=True, frames=149, failed_reason=None

RobotState shape check
-> root_pos (3,), root_quat (4,), dof_pos (23,), RobotState read OK

short reference track
-> track result: success=True, frames=99; Smoke track passed.

continuous two-track check
-> State delta 1: 0.303301; State delta 2: 0.304039; Continuous track state check passed.
```

**运行方式**：

```bash
python scripts/run_single_gmt_motion.py --motion walk_stand.pkl --duration 3.0
```

**风险**：当前 runner 已通过短 smoke，但 Windows 仍不是 GMT 官方验证平台；端到端长序列的稳定性要等 M4 运行结果确认。

---

## M2 Task Plan 记录

**范围**：实现 `task_plan/skill_plan.py`、`task_plan/skill_registry.py`，创建固定任务配置 `configs/sequences/demo_walk_kick_crouch_stand.yaml` 和 `configs/skills.yaml`。

**关键决策**：

- `SkillPlan.sequence` 保持四段：`walk_forward(10s) -> kick_leg -> crouch_down -> stand_up`。
- `walk_forward` 使用 `assets/motions/basic_walk.pkl`，duration=10.0 后续由 matcher 转成 300 帧。
- `kick_leg` 同时 smoke 了 `airkick_stand.pkl` 和 `kick_walk.pkl`，两者 2 秒 smoke 都返回 `success=True`；默认选择 `airkick_stand.pkl`，因为当前 transition 设计会先从 walking bridge 到 stable standing，再执行 standing kick，语义更匹配。
- `kick_leg`、`crouch_down`、`stand_up` 的 `default_end_frame` 暂为 `null`，即整段测试；这与 Prompt.md Done When 中“根据 motion 长度核验结果设置或明确保留为整段测试”一致。

**修改文件**：

```text
task_plan/skill_plan.py
task_plan/skill_registry.py
configs/skills.yaml
configs/sequences/demo_walk_kick_crouch_stand.yaml
Documentation.md
```

**Validation 结果**：

```text
G:\App\Miniconda\envs\gmt\python.exe -m py_compile task_plan/skill_plan.py task_plan/skill_registry.py
-> exit 0

parse_task_sequence validation
-> task_id: demo_walk_kick_crouch_stand; sequence length: 4; SkillPlan parsed OK.

SkillRegistry validation
-> walk_forward/kick_leg/crouch_down/stand_up all found; SkillRegistry validation passed.

kick_leg candidate smoke
-> airkick_stand.pkl: success=True, frames=99
-> kick_walk.pkl: success=True, frames=99
```

**运行方式**：

```bash
python -c "from task_plan.skill_plan import parse_task_sequence; print(parse_task_sequence('configs/sequences/demo_walk_kick_crouch_stand.yaml'))"
```

---

## M3 Middle Architecture 记录

**范围**：完成 motion 读取、reference 切片/插值/拼接、transition registry/builder、static matcher、root reanchor 分支。

**关键决策**：

- `GMTMotion.root_rot` 与 `ReferenceFrames.root_rot` 采用 M0 的 GMT pkl `xyzw` 顺序。
- `RobotState.root_quat` 采用 MuJoCo `qpos[3:7]` 的 `wxyz` 顺序；从 RobotState 插值到 reference 时转换为 `xyzw`。
- `reanchor_reference_frames()` 支持 `root_relative/pass_through` 和 `absolute_root/offset_root_pos`。默认由 M0 选择 `root_relative`，不重锚 skill clip；absolute-root 分支实现 yaw+translation 对齐，以保留 Prompt.md 要求的条件分支。
- interpolation transition 直接从当前真实 `RobotState` 插值到下一段入口帧。
- bridge transition 展开为 pre interpolation + bridge pkl slice + post interpolation；post 从 bridge motion 运动学末帧插到目标入口帧，这仍是第一版已知局限。

**修改文件**：

```text
middle_architecture/gmt_motion_adapter.py
middle_architecture/reference_ops.py
middle_architecture/robot_state.py
middle_architecture/matcher.py
middle_architecture/transition_registry.py
middle_architecture/transition_builder.py
configs/transitions.yaml
Documentation.md
```

**Validation 结果**：

```text
py_compile middle_architecture/*.py
-> exit 0

GMTMotion load
-> walk_stand.pkl: fps=29.932279909706544, root_pos=(222,3), root_rot=(222,4), dof_pos=(222,23), local_body_pos=(222,38,3)

slice basic_walk 0:300
-> ReferenceFrames: 300 frames; 300-frame slice OK.

interpolate from RobotState
-> Interpolated ReferenceFrames: 20 frames; OK.

concat
-> Concat frames: 20; OK.

TransitionRegistry
-> bridge walk_forward->kick_leg, interpolation kick_leg->crouch_down, interpolation crouch_down->stand_up; missing stand_up->walk_forward raises KeyError.

TransitionBuilder
-> constructor signature OK; interpolation frames=20; bridge frames=257.

MotionMatcher
-> walk_forward duration 10.0 produces end_frame=300.

reanchor
-> function exists; absolute-root first root aligns to current state; root_relative returns pass-through.
```

**运行方式**：

```bash
python -c "from middle_architecture.transition_registry import TransitionRegistry; print(TransitionRegistry.from_yaml('configs/transitions.yaml').get('walk_forward','kick_leg'))"
```

---

## M4 端到端集成记录

**范围**：实现 `HarnessOrchestrator` 和 `scripts/run_harness_sequence.py`，串联 Task Plan -> Middle Architecture -> Low Level Execution。

**执行结果**：单次 `GMTTrackingRunner.initialize()` 后，在同一个 MuJoCo model/data 中连续执行 4 个 skill 和 3 个 transition，全部返回 `success=True`。

**修改文件**：

```text
middle_architecture/harness_orchestrator.py
scripts/run_harness_sequence.py
Documentation.md
```

**Validation 结果**：

```text
py_compile middle_architecture/harness_orchestrator.py scripts/run_harness_sequence.py
-> exit 0

python scripts/run_harness_sequence.py
-> skill_001_walk_forward success=True
-> transition_001_walk_forward_to_kick_leg success=True
-> skill_002_kick_leg success=True
-> transition_002_kick_leg_to_crouch_down success=True
-> skill_003_crouch_down success=True
-> transition_003_crouch_down_to_stand_up success=True
-> skill_004_stand_up success=True

outputs check
-> outputs/demo_walk_kick_crouch_stand contains run_summary.json, execution_log.json, 4 skill dirs, 3 transition dirs

import chain
-> All imports successful.

reference shape check
-> walk_forward 300, kick_leg 200 full motion, crouch_down 304 full motion, stand_up 222 full motion
```

**运行方式**：

```bash
python scripts/run_harness_sequence.py
```

**输出位置**：

```text
outputs/demo_walk_kick_crouch_stand/
```

---

## M5 产物收敛记录

**范围**：运行最终全量核验脚本，检查交付文件、配置、motion assets、模块、脚本、M0 contract 和 outputs。

**文档冲突处理**：M5 final verification 要求 `scripts/inspect_gmt_motion_format.py` 存在；Implement.md 的 M5 表写“无新文件”。按用户给定优先级，Plan.md final validation 高于 Implement.md 白名单，因此补齐该架构内脚本并记录冲突。脚本只读取 pkl 并打印字段/shape，不引入架构外能力。

**Done When 覆盖**：

```text
1-3 配置与资产：configs/sequences、configs/skills.yaml、8 个 assets/motions pkl 均存在。
4-6 M0 契约：outputs/contract/GMT_obs_reference_contract.md 存在；root_reference_mode=root_relative；reanchor 分支按 M0 默认 pass-through。
7 Task Plan：SkillPlan 可输出并经 registry 校验。
8-16 Motion/Reference：motion adapter、get_kinematic_frame、slice/interpolate/concat/reanchor 均通过 validation。
17-29 Transition：TransitionRegistry、TransitionBuilder、interpolation/bridge transition reference_frames 均可生成，bridge post 简化已记录为已知局限。
30-37 Low Level Execution：runner 初始化一次，连续 track 不 reset，RobotState 从 live MuJoCo data 读取，fall detection 可返回 failed_reason='fell'。
38-40 集成与输出：outputs/demo_walk_kick_crouch_stand/ 写入日志；run_harness_sequence.py import 链完整；端到端 7 段全部 success。
```

**最终验证结果**：

```text
scripts/inspect_gmt_motion_format.py assets/motions/walk_stand.pkl
-> fps/root_pos/root_rot/dof_pos/local_body_pos/link_body_list 均可读取并打印 shape。

Plan.md M5 final verification script
-> All checks passed.
```

**Git 状态**：当前 `G:\Code\Python\HumaSkill` 不是 git repository，因此没有 merge/commit/PR 分支收尾动作。

## 已知局限与风险

### 1. Windows 未验证

- **影响**：MuJoCo 图形窗口、路径分隔符、依赖库行为可能与 Linux/macOS 不一致。
- **当前处理**：`configs/harness.yaml` 的 `platform.windows_status: unverified`。若在 Windows 上运行出错，优先在 Linux 或 WSL 下验证。
- **缓解**：GMT 官方已验证 Linux 和 M1 macOS，Windows 不阻塞主链路但需单独核验。

### 2. 衔接处稳定性未保证

- **影响**：interpolation 模式仅做运动学插值（lerp + slerp），不做动力学可行性检查。bridge 模式的 post 段从 bridge_motion 运动学末帧插值到下一段入口帧，可能包含不连续的速度跳变。
- **当前处理**：文档中标注为已知局限。第一版目标是"跑通"，不是"跑得稳定流畅"。
- **后续**：若衔接处经常摔倒，需考虑延长 interpolation 帧数、调整 bridge 参数或引入动力学约束。

### 3. 成功判定较粗

- **影响**：当前成功判定仅为"episode 跑完 + 未触发摔倒判据"。不评估动作质量、跟踪精度或各段完成度。
- **当前处理**：这是第一版的合理边界——先确认链路能通，再细化质量评估。
- **后续**：可加入 per-skill 的跟踪误差统计（如 root 位置偏差、dof 角度偏差）。

### 4. obs 必须原样复用 GMT

- **影响**：所有 obs 构造（历史窗口、归一化、参考速度差分、local_body_pos 有无）必须与 GMT policy 的训练配置一致。任何偏差都会导致 tracking 质量下降或完全失效。
- **当前处理**：M0 契约调查专门回答这些问题。runner 的 observation 构造严格复刻 `sim2sim.py`。
- **风险**：若 M0 调查遗漏某个 obs 细节，runner 的 tracking 行为会偏离预期。

### 5. bridge 的 post 段为运动学简化

- **影响**：bridge transition 的 post 段从 bridge_motion 的末帧运动学状态插值到目标入口帧。这不是物理模拟，不保证 tracking policy 能稳定追踪。
- **当前处理**：架构文档已记录为"已知局限"。第一版接受此简化。
- **后续**：如果 bridge post 段经常触发摔倒，可尝试缩短 post 帧数或完全去除 post 段。

### 6. 插值接缝速度不连续

- **影响**：interpolation transition 的最后一帧与下一段 skill 的首帧在位置上是连续的，但速度可能不连续（因为 interpolation 不保证速度连续性，且下一段 reference 的速度取决于 pkl 原始数据）。
- **当前处理**：架构文档标注为已知局限。tracking policy 的闭环特性一定程度上容忍速度跳变。
- **后续**：可引入速度平滑或 velocity-aware interpolation。

### 7. 各 motion clip 长度待核实

- **影响**：`kick_leg`（`airkick_stand.pkl`）、`crouch_down`（`squat.pkl`）、`stand_up`（`walk_stand.pkl`）的 `default_end_frame` 当前为 `null`（整段执行）。实际长度未核实，可能过长或过短。
- **当前处理**：M0 完成 + `inspect_gmt_motion_format.py` 核验后回填具体帧数。第一轮先整段测试，观察 tracking 效果再决定是否截断。
- **已确定**：`walk_forward` → `basic_walk.pkl`，截取前 300 帧（= 10s @ 30fps）。

### 8. root 重锚策略待 M0 确认

- **影响**：若 M0 结论为 absolute root 但未重锚，reference 的 root 位置与实际机器人 root 位置不一致，tracking 会失败。
- **当前处理**：两种分支都实现，M0 后选定。代码中不二选一写死。

### 9. 无失败恢复

- **影响**：任何一段 `track()` 返回 `success=False`（摔倒），整个任务即中止。不会尝试回退、切换备选路径或重试。
- **当前处理**：第一版不包含复杂失败恢复，这属于"后续"范围。

### 10. matcher 为静态第一版

- **影响**：`MotionMatcher` 当前不根据 `RobotState` 做匹配，只使用 `SkillSpec` 中预设的 `motion_file` 和 `default_start_frame`。
- **当前处理**：接口保留 `robot_state` 参数，但第一版逻辑不消费它。后续可扩展为基于状态的动态匹配。

---

## 后续规划（非第一版范围）

```text
- 语言规划（自然语言→SkillPlan）
- 基于 RobotState 的动态 motion 匹配（D = λq·Dq + λroot·Droot + λv·Dv + λc·Dc）
- 复杂失败恢复策略
- 自动 skill graph 搜索
- 衔接质量打分
- 训练 policy、retarget 动作数据、真机部署
- 仿真视频录制
- Windows 环境完整验证
```

---

## 变更日志

| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-06-03 | 文档初始创建 | 基于 `Architecture_Desgin.md` 产出四份交付文档 |
| 2026-06-03 | 确定 kick_leg → airkick_stand.pkl | 任务链路设计了 stable_stand_bridge，空中踢腿更匹配 |
| 2026-06-03 | 确定 crouch_down → squat.pkl | 语义更直接，crouchwalk_stand 保留为 bridge 备用 |
| 2026-06-03 | 确定 device 优先 CPU | 减少 CUDA 变量，先验证 runner 逻辑 |
| 2026-06-03 | 视频不作为硬性交付物 | 先验收核心链路，视频后续补充 |
| 2026-06-03 | walk_forward default_end_frame 设为 300 | 10s @ 30fps = 300 帧，架构文档 matcher 段已确认 |
| 2026-06-03 | 完成 M0 obs/reference 契约调查 | 生成 contract 并确认 root_reference_mode=`root_relative`、motion root_rot=`xyzw` |
| 2026-06-03 | 完成 M1 GMTTrackingRunner | runner smoke、RobotState shape、短 reference track、连续 track 均通过 |
| 2026-06-03 | 完成 M2 Task Plan 层 | 固定 YAML 任务和 skill registry 可解析、可校验 |
| 2026-06-03 | 完成 M3 Middle Architecture 层 | motion/reference/transition/matcher/root reanchor 分项 validation 均通过 |
| 2026-06-03 | 完成 M4 端到端集成 | 4 skill + 3 transition 在同一个 runner episode 内全部 success |
| 2026-06-03 | 完成 M5 产物收敛 | final verification 全部 OK，Documentation 更新到最终状态 |
