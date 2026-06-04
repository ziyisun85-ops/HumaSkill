# Plan — HumaSkill 第一版开发计划

> 本文档是 `Architecture_Desgin.md` 的开发执行计划。每个 milestone 按严格顺序执行，
> 带有明确的 acceptance criteria 和可直接运行的 validation commands。
> M0 是硬门槛 — M0 不过，不准进入 M1 及之后任何 milestone。

---

## P0：人工前置 — 验证 GMT 原始环境

**目标**：确认 GMT `sim2sim.py` 在当前环境中可以运行单 motion。

**Acceptance Criteria**：
- `python sim2sim.py --robot g1 --motion walk_stand.pkl` 能跑通，G1 机器人出现并开始跟踪参考动作。
- 若命令失败，暂停 harness 主链路开发，先修复 GMT 环境（依赖、MuJoCo、Python 版本等）。

**Validation Command**：

```bash
cd G:/Code/Python/Paper-Reproduction/GMT/humanoid-general-motion-tracking
python sim2sim.py --robot g1 --motion walk_stand.pkl
```

**输出**：口头确认通过 / 环境错误日志。

**责任人**：人工（非 Codex）。

---

## M0：GMT obs/reference 契约调查（硬门槛）

**目标**：阅读 GMT `sim2sim.py` 源码，产出《GMT obs/reference 契约结论》，
回答后续所有 milestone 依赖的底层事实。

**依赖**：P0 通过。

**Acceptance Criteria**：

`outputs/contract/GMT_obs_reference_contract.md` 文件存在且至少回答以下 9 个问题：

| # | 问题 | 为什么重要 |
|---|------|-----------|
| 1 | 如何只加载一次 policy + mujoco，并在不 reset 的前提下连续步进？ | M1 runner 的 initialize/track 语义 |
| 2 | policy observation 的参考目标是绝对 root，还是 root 相对量、速度量？ | M3 root 重锚分支选择 |
| 3 | skill clip 与 transition 是否需要重锚到当前真实 root？ | M3 reanchor 启用判定 |
| 4 | 控制频率、物理频率、decimation 分别是什么？ | M1 track() 步进循环 |
| 5 | 参考 30fps 如何按时间索引到控制步？ | M1 参考帧→控制步映射 |
| 6 | obs 是否带历史窗口？ | M1 observation 构造 |
| 7 | obs normalization 如何加载和应用？ | M1 observation normalization |
| 8 | reference velocity 是否需要由参考序列差分得到？ | M3 reference_ops 速度派生 |
| 9 | `local_body_pos` 在 observation 中是否必需？ | M3 interpolate 的 local_body_pos 策略 |

**Validation Commands**：

```bash
# 运行契约调查脚本
python scripts/inspect_gmt_obs_reference_contract.py ^
  --gmt-root G:/Code/Python/Paper-Reproduction/GMT/humanoid-general-motion-tracking ^
  --sim2sim sim2sim.py ^
  --output outputs/contract/GMT_obs_reference_contract.md
```

```bash
# 核验输出文件存在且内容非空
python -c "
import os
path = 'outputs/contract/GMT_obs_reference_contract.md'
assert os.path.exists(path), 'M0 contract file missing'
size = os.path.getsize(path)
assert size > 500, f'M0 contract too small: {size} bytes'
print(f'M0 contract OK: {size} bytes')
"
```

```bash
# 额外核验：确认所有 9 个问题在输出中有对应回答
python -c "
with open('outputs/contract/GMT_obs_reference_contract.md', encoding='utf-8') as f:
    text = f.read()
questions = [
    '加载', 'reset', '连续步进',
    '绝对 root', 'root 相对', 'root_relative', 'absolute_root',
    '重锚', 'reanchor',
    '控制频率', '物理频率', 'decimation',
    '时间索引', '30fps',
    '历史窗口', 'history',
    'normalization', '归一化',
    '速度', 'velocity', '差分',
    'local_body_pos',
]
found = [q for q in questions if q.lower() in text.lower()]
missing = [q for q in questions if q.lower() not in text.lower()]
if missing:
    print(f'WARNING: keywords not found in contract: {missing}')
else:
    print('All expected keywords found in M0 contract.')
"
```

**输出**：`outputs/contract/GMT_obs_reference_contract.md`

**门禁规则**：M0 contract 不存在或内容不足 → **不得进入 M1**。

---

## M1：GMTTrackingRunner 重构

**目标**：基于 M0 结论，复刻 `sim2sim.py` 的步进逻辑，实现可 import 的 `GMTTrackingRunner`。

**依赖**：M0 通过。

**Acceptance Criteria**：

1. `low_level_execution/gmt_tracking_runner.py` 可 import。
2. `GMTTrackingRunner.__init__()` 只加载一次 MuJoCo env 和 policy。
3. `initialize()` 完成环境初始化，不被 `track()` 重复调用。
4. `track(reference_frames)` 按 M0 结论的控制频率/物理频率/decimation 步进。
5. 参考 30fps 到控制步的时间索引方式与 `sim2sim.py` 一致。
6. observation 构造（含历史窗口和归一化）与 `sim2sim.py` 一致。
7. `get_robot_state()` 返回真实 MuJoCo data 中的 `RobotState`。
8. `_has_fallen()` 检测 root 高度和机身倾角。
9. 摔倒时返回 `success=False, failed_reason="fell"`。
10. 正常结束时返回 `success=True`。

**Validation Commands**：

```bash
# Smoke test：单 motion 3 秒跟踪
python scripts/run_single_gmt_motion.py --motion walk_stand.pkl --duration 3.0
```

```bash
# 核验：track 后 RobotState 非空且 shape 正确
python -c "
from low_level_execution.gmt_tracking_runner import GMTTrackingRunner
runner = GMTTrackingRunner(
    gmt_root='G:/Code/Python/Paper-Reproduction/GMT/humanoid-general-motion-tracking',
    robot='g1',
    device='auto',
)
runner.initialize()
state = runner.get_robot_state()
print('RobotState fields:')
print(f'  root_pos shape: {state.root_pos.shape}')
print(f'  root_quat shape: {state.root_quat.shape}')
print(f'  dof_pos shape:  {state.dof_pos.shape}')
print('RobotState read OK.')
"
```

```bash
# 核验：track 短参考帧后不报错，返回 success
python -c "
from low_level_execution.gmt_tracking_runner import GMTTrackingRunner
from middle_architecture.gmt_motion_adapter import load_gmt_motion
from middle_architecture.reference_ops import slice_motion_to_reference_frames

runner = GMTTrackingRunner(
    gmt_root='G:/Code/Python/Paper-Reproduction/GMT/humanoid-general-motion-tracking',
    robot='g1',
    device='auto',
)
runner.initialize()

m = load_gmt_motion('assets/motions/walk_stand.pkl')
rf = slice_motion_to_reference_frames(m, 0, 60)
result = runner.track(rf)
print(f'track result: success={result.success}, frames={result.num_frames}')
assert result.success, 'track should succeed on short motion'
print('Smoke track passed.')
"
```

```bash
# 核验：连续两次 track 之间物理状态不 reset
python -c "
from low_level_execution.gmt_tracking_runner import GMTTrackingRunner
from middle_architecture.gmt_motion_adapter import load_gmt_motion
from middle_architecture.reference_ops import slice_motion_to_reference_frames

runner = GMTTrackingRunner(
    gmt_root='G:/Code/Python/Paper-Reproduction/GMT/humanoid-general-motion-tracking',
    robot='g1',
    device='auto',
)
runner.initialize()

m = load_gmt_motion('assets/motions/walk_stand.pkl')
rf1 = slice_motion_to_reference_frames(m, 0, 30)
rf2 = slice_motion_to_reference_frames(m, 0, 30)

state_before = runner.get_robot_state()
runner.track(rf1)
state_mid = runner.get_robot_state()
runner.track(rf2)
state_after = runner.get_robot_state()

# 状态应该变化（物理在演化）
import numpy as np
d1 = np.linalg.norm(state_mid.root_pos - state_before.root_pos)
d2 = np.linalg.norm(state_after.root_pos - state_mid.root_pos)
print(f'State delta 1: {d1:.6f}')
print(f'State delta 2: {d2:.6f}')
assert d1 > 1e-6 or d2 > 1e-6, 'State should change between tracks'
print('Continuous track state check passed.')
"
```

**输出**：可工作的 `GMTTrackingRunner`，通过单 motion smoke test 和连续 track 测试。

---

## M2：Task Plan 层

**目标**：从 YAML 任务配置产出 `SkillPlan`，含 skill registry 校验。

**依赖**：无（可独立于 M1 完成）。

**Acceptance Criteria**：

1. `task_plan/skill_plan.py` 定义 `SkillPlan` dataclass 和 `parse_task_sequence()`。
2. `task_plan/skill_registry.py` 定义 `SkillRegistry`，`from_yaml()` 加载 `configs/skills.yaml`。
3. `SkillRegistry.has(skill_name)` 返回 True/False。
4. `SkillRegistry.validate(skill_plan)` 检查所有 skill 名在 registry 中存在。
5. 读取 `configs/sequences/demo_walk_kick_crouch_stand.yaml` 并产出 `SkillPlan`。

**Validation Commands**：

```bash
# 核验：parse_task_sequence 产出 SkillPlan
python -c "
from task_plan.skill_plan import parse_task_sequence
plan = parse_task_sequence('configs/sequences/demo_walk_kick_crouch_stand.yaml')
print(f'task_id: {plan.task_id}')
print(f'sequence length: {len(plan.sequence)}')
for item in plan.sequence:
    print(f'  skill={item.skill}, duration={item.duration}')
assert plan.task_id == 'demo_walk_kick_crouch_stand'
assert len(plan.sequence) == 4
print('SkillPlan parsed OK.')
"
```

```bash
# 核验：SkillRegistry 加载并校验
python -c "
from task_plan.skill_registry import SkillRegistry
from task_plan.skill_plan import parse_task_sequence

registry = SkillRegistry.from_yaml('configs/skills.yaml')
plan = parse_task_sequence('configs/sequences/demo_walk_kick_crouch_stand.yaml')

for item in plan.sequence:
    assert registry.has(item.skill), f'Skill {item.skill} not in registry'
    print(f'  {item.skill}: OK (motion={registry.get(item.skill).motion_file})')

print('SkillRegistry validation passed.')
"
```

**输出**：可工作的 Task Plan 层。

---

## M3：Middle Architecture 层

**目标**：实现 motion 读取、reference 操作、transition 构造和 root 重锚。

**依赖**：M0 通过（M2 可并行完成，但 root 重锚策略依赖 M0 结论）。

### M3a：gmt_motion_adapter + reference_ops

**Acceptance Criteria**：

1. `load_gmt_motion()` 读取 pkl 返回 `GMTMotion`。
2. `get_kinematic_frame()` 提取指定帧的 `KinematicFrame`。
3. `slice_motion_to_reference_frames()` 切帧输出 `ReferenceFrames`。
4. `interpolate_reference_frames()` 支持 `RobotState` 和 `KinematicFrame` 两种起点。
5. `concat_reference_frames()` 拼接多段 `ReferenceFrames`。
6. `reanchor_reference_frames()` 已实现（启用条件由 M0 结论决定）。

**Validation Commands**：

```bash
# 核验：load_gmt_motion 读取所有字段
python -c "
from middle_architecture.gmt_motion_adapter import load_gmt_motion

m = load_gmt_motion('assets/motions/walk_stand.pkl')
print(f'name: {m.name}')
print(f'fps: {m.fps}')
print(f'root_pos shape: {m.root_pos.shape}')
print(f'root_rot shape: {m.root_rot.shape}')
print(f'dof_pos shape: {m.dof_pos.shape}')
print(f'local_body_pos shape: {m.local_body_pos.shape if m.local_body_pos is not None else None}')
print(f'num_frames: {m.num_frames}')
assert m.fps > 0
assert m.root_pos.ndim == 2 and m.root_pos.shape[1] == 3
assert m.root_rot.ndim == 2 and m.root_rot.shape[1] == 4
assert m.dof_pos.ndim == 2
print('GMTMotion load OK.')
"
```

```bash
# 核验：slice_motion_to_reference_frames 截取 300 帧
python -c "
from middle_architecture.gmt_motion_adapter import load_gmt_motion
from middle_architecture.reference_ops import slice_motion_to_reference_frames

m = load_gmt_motion('assets/motions/basic_walk.pkl')
rf = slice_motion_to_reference_frames(m, 0, 300)
print(f'ReferenceFrames: {rf.root_pos.shape[0]} frames')
assert rf.root_pos.shape[0] == 300, f'Expected 300 frames, got {rf.root_pos.shape[0]}'
assert abs(rf.fps - 30.0) < 0.1
print('300-frame slice OK.')
"
```

```bash
# 核验：interpolate_reference_frames 以 RobotState 为起点
python -c "
import numpy as np
from middle_architecture.robot_state import RobotState
from middle_architecture.gmt_motion_adapter import load_gmt_motion, get_kinematic_frame
from middle_architecture.reference_ops import interpolate_reference_frames

m = load_gmt_motion('assets/motions/walk_stand.pkl')
target_frame = get_kinematic_frame(m, 10)

start = RobotState(
    root_pos=np.zeros(3),
    root_quat=np.array([1.0, 0.0, 0.0, 0.0]),
    dof_pos=np.zeros_like(m.dof_pos[0]),
    root_lin_vel=np.zeros(3),
    root_ang_vel=np.zeros(3),
    dof_vel=np.zeros_like(m.dof_pos[0]),
)

rf = interpolate_reference_frames(start, target_frame, num_frames=20, fps=30.0)
print(f'Interpolated ReferenceFrames: {rf.root_pos.shape[0]} frames')
assert rf.root_pos.shape[0] == 20
print('Interpolation from RobotState OK.')
"
```

```bash
# 核验：concat_reference_frames 拼接
python -c "
from middle_architecture.gmt_motion_adapter import load_gmt_motion
from middle_architecture.reference_ops import slice_motion_to_reference_frames, concat_reference_frames

m = load_gmt_motion('assets/motions/walk_stand.pkl')
rf1 = slice_motion_to_reference_frames(m, 0, 10)
rf2 = slice_motion_to_reference_frames(m, 10, 20)
rf_cat = concat_reference_frames([rf1, rf2])
print(f'Concat frames: {rf_cat.root_pos.shape[0]}')
assert rf_cat.root_pos.shape[0] == 20
print('Concat OK.')
"
```

### M3b：transition_registry + transition_builder

**Acceptance Criteria**：

1. `TransitionRegistry.from_yaml()` 加载 `configs/transitions.yaml`。
2. `TransitionRegistry.get(from_skill, to_skill)` 返回 `TransitionSpec`。
3. 未配置的 transition 抛出明确异常。
4. `TransitionBuilder.build_transition()` 支持 `interpolation` 和 `bridge` 两种 mode。
5. interpolation 模式下生成指定帧数的插值 reference_frames。
6. bridge 模式下正确构造 pre + bridge + post 三段式 reference_frames。
7. transition 的 `reference_frames` 可直接传给 `track()`。

**Validation Commands**：

```bash
# 核验：TransitionRegistry 加载
python -c "
from middle_architecture.transition_registry import TransitionRegistry

reg = TransitionRegistry.from_yaml('configs/transitions.yaml')
spec = reg.get('walk_forward', 'kick_leg')
print(f'walk_forward→kick_leg: mode={spec.mode}, bridge_skill={spec.bridge_skill}')

spec2 = reg.get('kick_leg', 'crouch_down')
print(f'kick_leg→crouch_down: mode={spec2.mode}, num_frames={spec2.num_frames}')

spec3 = reg.get('crouch_down', 'stand_up')
print(f'crouch_down→stand_up: mode={spec3.mode}, num_frames={spec3.num_frames}')

print('TransitionRegistry OK.')
"
```

```bash
# 核验：未配置的 transition 抛异常
python -c "
from middle_architecture.transition_registry import TransitionRegistry

reg = TransitionRegistry.from_yaml('configs/transitions.yaml')
try:
    reg.get('stand_up', 'walk_forward')
    print('ERROR: should have raised')
except Exception as e:
    print(f'Correctly raised: {type(e).__name__}: {e}')
"
```

```bash
# 核验：build_interpolation_transition
python -c "
import numpy as np
from middle_architecture.gmt_motion_adapter import load_gmt_motion, get_kinematic_frame
from middle_architecture.robot_state import RobotState
from middle_architecture.transition_builder import TransitionBuilder

motion_adapter_stub = None  # 实际测试使用真实 adapter
# 此处为占位 — 具体 validation 在 M4 集成测试中执行
print('TransitionBuilder import check passed.')
"
```

```bash
# 核验：TransitionBuilder 构造参数与入口脚本一致
python -c "
from middle_architecture.gmt_motion_adapter import GmtMotionAdapter
from middle_architecture.transition_builder import TransitionBuilder
from middle_architecture.transition_registry import TransitionRegistry

# 模拟入口脚本的构造方式
motion_source = GmtMotionAdapter('assets/motions')
reg = TransitionRegistry.from_yaml('configs/transitions.yaml')
builder = TransitionBuilder(motion_source=motion_source, motion_adapter=motion_source)
print(f'TransitionBuilder created with motion_source={type(motion_source).__name__}')
print('Constructor signature check passed.')
"
```

### M3c：Motion Matcher

**Acceptance Criteria**：

1. `MotionMatcher.select()` 根据 `SkillSpec` 返回 `MatchResult`。
2. 第一版为静态匹配：使用 `SkillSpec` 中声明的 `motion_file`，默认 `default_start_frame`。
3. `duration` 存在时按 fps 计算 `end_frame`。

**Validation Commands**：

```bash
# 核验：matcher 产出 MatchResult
python -c "
from middle_architecture.gmt_motion_adapter import load_gmt_motion
from middle_architecture.matcher import MotionMatcher
from task_plan.skill_registry import SkillRegistry

reg = SkillRegistry.from_yaml('configs/skills.yaml')
spec = reg.get('walk_forward')
motion = load_gmt_motion(spec.motion_file)

matcher = MotionMatcher()
result = matcher.select(robot_state=None, skill_spec=spec, motion=motion, duration=10.0)
print(f'motion_path: {result.motion_path}')
print(f'start_frame: {result.start_frame}')
print(f'end_frame: {result.end_frame}')
assert result.end_frame == 300
print('Matcher OK.')
"
```

### M3d：Root 重锚

**Acceptance Criteria**：

1. `reanchor_reference_frames()` 已实现，支持两种模式。
2. 若 M0 结论为 absolute root：skill clip 和 transition target entry 都重锚到当前真实 root。
3. 若 M0 结论为 root relative / 速度量：`reanchor_reference_frames()` 存在但不调用（或调用时直接 pass-through）。
4. `reanchor_yaw_only` 选项可配置。

**Validation Commands**：

```bash
# 核验：reanchor 函数存在且可调用
python -c "
from middle_architecture.reference_ops import reanchor_reference_frames
print('reanchor_reference_frames function exists.')
# 具体行为验证依赖 M0 结论，在 M4 集成测试中覆盖
"
```

**输出**：完整的 Middle Architecture 层。

---

## M4：端到端集成

**目标**：将所有模块串通，在单 episode 内跑完 walk_forward → kick_leg → crouch_down → stand_up。

**依赖**：M0、M1、M2、M3 全部通过。

**Acceptance Criteria**：

1. `scripts/run_harness_sequence.py` 可以 import 所有模块并通过方法签名检查。
2. 单次运行 `run_harness_sequence.py` 在同一个 MuJoCo episode 中执行全部 4 个 skill + 3 个 transition。
3. 每段执行后 `RobotState` 成功回传。
4. transition reference_frames 成功生成（bridge + interpolation × 2）。
5. 序列从头跑到尾，无 import 错误、无运行时崩溃。
6. 执行日志保存到 `outputs/`。

**Validation Commands**：

```bash
# 端到端运行
python scripts/run_harness_sequence.py
```

```bash
# 核验：outputs 中有执行日志
python -c "
import os
output_dir = 'outputs/demo_walk_kick_crouch_stand'
if os.path.exists(output_dir):
    files = os.listdir(output_dir)
    print(f'Output files ({len(files)}):')
    for f in files:
        print(f'  {f}')
else:
    print('WARNING: output directory not found.')
"
```

```bash
# 核验：import 链条完整
python -c "
# Task Plan
from task_plan.skill_plan import parse_task_sequence, SkillPlan
from task_plan.skill_registry import SkillRegistry

# Middle Architecture
from middle_architecture.gmt_motion_adapter import load_gmt_motion, GmtMotionAdapter, get_kinematic_frame
from middle_architecture.reference_ops import slice_motion_to_reference_frames, interpolate_reference_frames, concat_reference_frames, reanchor_reference_frames
from middle_architecture.robot_state import RobotState, KinematicFrame
from middle_architecture.matcher import MotionMatcher
from middle_architecture.transition_registry import TransitionRegistry
from middle_architecture.transition_builder import TransitionBuilder
from middle_architecture.harness_orchestrator import HarnessOrchestrator

# Low Level Execution
from low_level_execution.gmt_tracking_runner import GMTTrackingRunner

print('All imports successful.')
"
```

```bash
# 核验：reference_frames shape 检查 — skill 段与 transition 段帧数合理
python -c "
from middle_architecture.gmt_motion_adapter import load_gmt_motion
from middle_architecture.reference_ops import slice_motion_to_reference_frames

# walk_forward: 300 frames
m_walk = load_gmt_motion('assets/motions/basic_walk.pkl')
rf_walk = slice_motion_to_reference_frames(m_walk, 0, 300)
print(f'walk_forward: {rf_walk.root_pos.shape[0]} frames')

# kick_leg: 整段（帧数待 M0 核验）
m_kick = load_gmt_motion('assets/motions/airkick_stand.pkl')
rf_kick = slice_motion_to_reference_frames(m_kick, 0, m_kick.num_frames)
print(f'kick_leg: {rf_kick.root_pos.shape[0]} frames (full motion)')

# crouch_down: 整段（帧数待 M0 核验）
m_squat = load_gmt_motion('assets/motions/squat.pkl')
rf_squat = slice_motion_to_reference_frames(m_squat, 0, m_squat.num_frames)
print(f'crouch_down: {rf_squat.root_pos.shape[0]} frames (full motion)')

# stand_up: 整段（帧数待 M0 核验）
m_stand = load_gmt_motion('assets/motions/walk_stand.pkl')
rf_stand = slice_motion_to_reference_frames(m_stand, 0, m_stand.num_frames)
print(f'stand_up: {rf_stand.root_pos.shape[0]} frames (full motion)')

print('All reference shapes checked.')
"
```

**输出**：端到端可运行的系统。

---

## M5：产物收敛与最终验证

**目标**：确认所有交付物完整、内部一致、验收标准全部通过。

**依赖**：M4 通过。

**Acceptance Criteria**：

1. `Documentation.md` 已更新至最新状态。
2. 所有 40 条验收标准（见 `Prompt.md` Done When）逐一检查通过。
3. 四个交付文档（`Prompt.md`、`Plan.md`、`Implement.md`、`Documentation.md`）与 `Architecture_Desgin.md` 无矛盾。
4. `outputs/` 中有 M0 contract 和执行日志。

**Validation Commands**：

```bash
# 最终全量核验脚本
python -c "
import os

checks = []

# 1. 文件存在性
for f in ['Prompt.md', 'Plan.md', 'Implement.md', 'Documentation.md']:
    checks.append((f'File {f}', os.path.exists(f)))

# 2. M0 contract
checks.append(('M0 contract', os.path.exists('outputs/contract/GMT_obs_reference_contract.md')))

# 3. 配置文件
for f in [
    'configs/skills.yaml',
    'configs/transitions.yaml',
    'configs/harness.yaml',
    'configs/sequences/demo_walk_kick_crouch_stand.yaml',
]:
    checks.append((f'Config {f}', os.path.exists(f)))

# 4. assets
motions_dir = 'assets/motions'
expected_motions = [
    'airkick_stand.pkl', 'basic_walk.pkl', 'crouchwalk_stand.pkl',
    'dance.pkl', 'dance_waltz.pkl', 'kick_walk.pkl',
    'squat.pkl', 'walk_stand.pkl',
]
if os.path.exists(motions_dir):
    for m in expected_motions:
        checks.append((f'Motion {m}', os.path.exists(os.path.join(motions_dir, m))))

# 5. 模块存在性
modules = [
    'task_plan/skill_plan.py',
    'task_plan/skill_registry.py',
    'middle_architecture/gmt_motion_adapter.py',
    'middle_architecture/reference_ops.py',
    'middle_architecture/robot_state.py',
    'middle_architecture/matcher.py',
    'middle_architecture/transition_registry.py',
    'middle_architecture/transition_builder.py',
    'middle_architecture/harness_orchestrator.py',
    'low_level_execution/gmt_tracking_runner.py',
]
for m in modules:
    checks.append((f'Module {m}', os.path.exists(m)))

# 6. Scripts
scripts = [
    'scripts/inspect_gmt_motion_format.py',
    'scripts/inspect_gmt_obs_reference_contract.py',
    'scripts/run_harness_sequence.py',
    'scripts/run_single_gmt_motion.py',
]
for s in scripts:
    checks.append((f'Script {s}', os.path.exists(s)))

print('=== Final Verification ===')
all_ok = True
for name, ok in checks:
    status = 'OK' if ok else 'MISSING'
    if not ok:
        all_ok = False
    print(f'  [{status}] {name}')

print()
if all_ok:
    print('All checks passed.')
else:
    print('SOME CHECKS FAILED — review above.')
"
```

**输出**：完整、可交付的 HumaSkill 第一版。

---

## Milestone 依赖图

```text
P0 (人工)
  ↓
M0 (硬门槛 — 不过不准往下)
  ↓
┌─────────────┐
│ M1 (runner) │    M2 (task_plan) ← 可并行
└──────┬──────┘         │
       └──────┬─────────┘
              ↓
       M3 (middle_architecture)
          M3a: gmt_motion_adapter + reference_ops
          M3b: transition_registry + transition_builder
          M3c: matcher
          M3d: root 重锚
              ↓
       M4 (端到端集成)
              ↓
       M5 (产物收敛)
```

M1 和 M2 可以在 M0 通过后并行执行。M3 依赖 M0（root 重锚策略）和 M2（SkillSpec），M4 依赖全部前置。

---

## 待定项（由 M0 决定）

以下配置值当前为占位，M0 后用实际数值回填：

| 配置项 | 当前值 | 位置 |
|--------|--------|------|
| `runner_timing.control_dt` | `pending_m0` | `configs/harness.yaml` |
| `runner_timing.physics_dt` | `pending_m0` | `configs/harness.yaml` |
| `runner_timing.decimation` | `pending_m0` | `configs/harness.yaml` |
| `runner_timing.reference_time_indexing` | `pending_m0` | `configs/harness.yaml` |
| `runner_timing.obs_history` | `pending_m0` | `configs/harness.yaml` |
| `runner_timing.obs_normalization` | `pending_m0` | `configs/harness.yaml` |
| `reference_contract.root_reference_mode` | `pending_m0` | `configs/harness.yaml` |
| `reference_contract.reanchor_skill_clip` | `pending_m0` | `configs/harness.yaml` |
| `reference_contract.reference_velocity_policy` | `pending_m0` | `configs/harness.yaml` |
| `reference_contract.local_body_pos_policy` | `pending_m0` | `configs/harness.yaml` |
| `fall_detection.min_root_height` | `pending_m0_or_empirical_config` | `configs/harness.yaml` |
| `fall_detection.max_body_tilt` | `pending_m0_or_empirical_config` | `configs/harness.yaml` |
| `kick_leg.default_end_frame` | `null`（整段） | `configs/skills.yaml` |
| `crouch_down.default_end_frame` | `null`（整段） | `configs/skills.yaml` |
| `stand_up.default_end_frame` | `null`（整段） | `configs/skills.yaml` |
