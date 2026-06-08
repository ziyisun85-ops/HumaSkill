# Implement — Codex 执行规则

> 本文档是给 Codex 的实现纪律手册。你不是在自由开发，你是在严格按 `Architecture_Desgin.md`（唯一事实来源）
> 和 `Plan.md`（有序 milestone）执行交付。每一行代码都要有据可查。

---

## 核心原则

### 1. 唯一事实来源

`Architecture_Desgin.md` 是唯一事实来源。其中已定的：

- 模块名、文件名、类名、方法签名
- 配置 YAML 的 key / value 结构
- 数据结构的字段和类型
- 三层职责边界
- 执行模型（常驻单 episode、可 import runner、段间不 reset）
- transition 模式（interpolation / bridge）
- root 重锚的条件分支

**直接采用，不要重新推导、不要改名、不要另立一套。**

### 2. M0 硬门槛

**M0 是所有后续工作的前提。M0 不过，不准进 M1 及之后任何 milestone。**

M0 的唯一产出是 `outputs/contract/GMT_obs_reference_contract.md`，通过阅读 GMT `sim2sim.py` 源码回答 9 个问题（见 `Plan.md` M0 章节）。

所有 GMT 相关数值——控制频率、物理频率、decimation、参考时间索引、obs 历史窗口、归一化方式、local_body_pos 是否必需、参考速度来源——**一律取自 M0 结论，不得编造**。

### 3. 严格 Milestone 顺序

按 `Plan.md` 中定义的 P0 → M0 → M1/M2 → M3 → M4 → M5 顺序执行。

每个 milestone 开始前，先检查前置依赖是否已通过：

```text
M0 开始前：确认 P0 通过（人工）
M1 开始前：确认 M0 contract 存在且内容完整
M2 开始前：确认 M0 contract 存在且内容完整（M2 不直接依赖 M1）
M3 开始前：确认 M0 通过 + M2 完成
M4 开始前：确认 M0、M1、M2、M3 全部通过
M5 开始前：确认 M4 通过
```

### 4. 每步先跑 Validation

进入一个 milestone 后，**先跑该 milestone 的 validation commands**（见 `Plan.md`），确认当前基线状态。实现完成后立刻重跑，验证通过才进入下一步。

**规则**：

```text
实现 → 跑 validation → 失败 → 修 → 重跑 → 通过 → 进入下个 milestone
```

不要跳过 validation，不要等全部写完了再一起测。

### 5. Diff 纪律

每次改动限制在当前 milestone 范围内：

- 不擅自重构已有模块。
- 不扩大改动面——只增不改已有接口（除非 M0 结论要求修改签名）。
- 不新增 `Architecture_Desgin.md` 中不存在的 `.py` 模块或 `.yaml` 文件。
- 不删除或重命名架构文档中已定义的文件。

新增文件白名单（仅在对应 milestone 中创建）：

| Milestone | 可新增文件 |
|-----------|-----------|
| M0 | `outputs/contract/GMT_obs_reference_contract.md`, `scripts/inspect_gmt_obs_reference_contract.py` |
| M1 | `low_level_execution/gmt_tracking_runner.py` |
| M2 | `task_plan/skill_plan.py`, `task_plan/skill_registry.py` |
| M3 | `middle_architecture/gmt_motion_adapter.py`, `middle_architecture/reference_ops.py`, `middle_architecture/robot_state.py`, `middle_architecture/matcher.py`, `middle_architecture/transition_registry.py`, `middle_architecture/transition_builder.py` |
| M4 | `middle_architecture/harness_orchestrator.py`, `scripts/run_harness_sequence.py`, `scripts/run_single_gmt_motion.py` |
| M5 | 无新文件，仅更新 `Documentation.md` |

### 6. 文档同步

每个 milestone 完成后，**立刻更新 `Documentation.md`**：

- 将该 milestone 标记为 `completed`。
- 记录关键决策和理由。
- 更新已知局限（如有新发现）。
- 记录 M0 结论中的关键数值（当 M0 完成时）。

`Documentation.md` 是活的——不能等到全部结束了再补。

---

## 各 Milestone 执行细则

### P0（人工 — 不执行）

P0 由人工在 GMT 仓库中执行。Codex 不执行此步骤。确认 P0 已通过后，从 M0 开始。

---

### M0：GMT obs/reference 契约调查

**关键指令**：

1. 读取 `G:/Code/Python/Paper-Reproduction/GMT/humanoid-general-motion-tracking/sim2sim.py`。
2. 追踪其中的 `track()` / `step()` / `get_observation()` / `compute_reward()` 调用链。
3. 找出控制频率、物理频率、decimation 的变量名和值。
4. 找出 observation 的构造方式（`compute_observations` 或等价函数）。
5. 判断参考目标中 root 是绝对坐标还是相对/速度量。
6. 判断 `local_body_pos` 在 obs 中是否必需。
7. 产出 `outputs/contract/GMT_obs_reference_contract.md`，覆盖 9 个问题。
8. 运行 `Plan.md` M0 中的 validation commands 确认输出。

**禁止**：

- 不看源码就写答案。
- 用 `sim2sim.py` 的命令行参数名代替实际变量值。
- 编造 decimation、control_dt 等数值。

---

### M1：GMTTrackingRunner 重构

**关键指令**：

1. 基于 M0 结论中"如何只加载一次并不 reset 连续步进"的答案，设计 `initialize()` / `track()` 边界。
2. 控制循环结构复刻 `sim2sim.py`：控制频率、物理频率、decimation、参考时间索引全部来自 M0 结论。
3. observation 构造（含历史窗口和归一化）与 `sim2sim.py` 一致。
4. `_has_fallen()` 使用可配置阈值（`configs/harness.yaml` 中的 `fall_detection` 节）。
5. 阈值当前为占位值（如 `min_root_height: 0.3`，`max_body_tilt: 45.0`），在 M0 和 smoke test 后调整。
6. `get_robot_state()` 从 `data.qpos` 和 `data.qvel` 中读取，不缓存在 Python 侧（要反映真实物理状态）。

**签名必须与架构文档一致**：

```python
class GMTTrackingRunner:
    def __init__(self, gmt_root, robot, device="auto"):
        ...

    def initialize(self):
        ...

    def track(self, reference_frames) -> RunnerTrackResult:
        ...

    def get_robot_state(self) -> RobotState:
        ...

    def _has_fallen(self) -> bool:
        ...
```

**禁止**：

- 在 `track()` 内部调用 `reset()`。
- 硬编码控制步进参数（必须读 M0 contract 或 harness.yaml）。
- 新增架构文档外的公开方法。

---

### M2：Task Plan 层

**关键指令**：

1. `SkillPlan` 和 `SkillPlanItem` 字段与架构文档 5.1 节一致。
2. `parse_task_sequence()` 读取 YAML 并构造 `SkillPlan`。
3. `SkillRegistry.from_yaml()` 加载 `configs/skills.yaml`。
4. `SkillRegistry.validate()` 检查所有 skill 名在 registry 中存在。

**签名必须与架构文档一致**：

```python
@dataclass
class SkillPlanItem:
    skill: str
    duration: Optional[float]

@dataclass
class SkillPlan:
    task_id: str
    sequence: list  # list[SkillPlanItem]

def parse_task_sequence(yaml_path: str) -> SkillPlan:
    ...

class SkillRegistry:
    @staticmethod
    def from_yaml(yaml_path: str) -> "SkillRegistry":
        ...

    def has(self, skill_name: str) -> bool:
        ...

    def get(self, skill_name: str) -> "SkillSpec":
        ...

    def validate(self, skill_plan: SkillPlan) -> None:
        ...
```

---

### M3：Middle Architecture 层

#### M3a：gmt_motion_adapter + reference_ops

**关键指令**：

1. `GMTMotion` 和 `GmtMotionAdapter` 字段与架构文档 5.2 节一致。
2. `load_gmt_motion()` 读取 pkl，校验必要字段（`fps`, `root_pos`, `root_rot`, `dof_pos`）。
3. `get_kinematic_frame()` 提取单帧的 `KinematicFrame`。
4. `slice_motion_to_reference_frames()` 切帧输出 `ReferenceFrames`。
5. `interpolate_reference_frames()` 使用 `_as_kinematic_view()` 统一 RobotState 和 KinematicFrame。
   - `root_pos`: lerp
   - `root_rot`: slerp（wxyz 顺序）
   - `dof_pos`: lerp
   - `local_body_pos`: 按 M0 结论决定处理方式
6. `concat_reference_frames()` 拼接多段 ReferenceFrames，fps 必须一致。
7. `reanchor_reference_frames()` 已实现，启用条件由 M0 结论决定。

**签名必须与架构文档一致**：

```python
@dataclass
class GMTMotion:
    name: str
    path: str
    fps: float
    root_pos: np.ndarray
    root_rot: np.ndarray
    dof_pos: np.ndarray
    local_body_pos: Optional[np.ndarray]
    num_frames: int

class GmtMotionAdapter:
    def __init__(self, motions_root: str):
        ...

    def load(self, motion_file: str) -> GMTMotion:
        ...

    def get_kinematic_frame(self, motion: GMTMotion, frame_index: int) -> KinematicFrame:
        ...

def load_gmt_motion(path: str) -> GMTMotion:
    ...

def get_kinematic_frame(motion: GMTMotion, frame_index: int) -> KinematicFrame:
    ...

def slice_motion_to_reference_frames(motion, start_frame, end_frame) -> ReferenceFrames:
    ...

def interpolate_reference_frames(start, target_frame, num_frames, fps) -> ReferenceFrames:
    ...

def concat_reference_frames(list_of_reference_frames) -> ReferenceFrames:
    ...

def reanchor_reference_frames(reference_frames, current_state, mode) -> ReferenceFrames:
    ...
```

**禁止**：

- `interpolate_reference_frames` 只接受 RobotState 不接受 KinematicFrame（两种都要支持）。
- 在 `slice_motion_to_reference_frames` 中修改 reference fps。
- 编造 local_body_pos 的 shape 或处理方式（必须按 M0 结论）。

#### M3b：transition_registry + transition_builder

**关键指令**：

1. `TransitionRegistry` 内部以 `(from_skill, to_skill)` 为键。
2. `TransitionBuilder.build_transition()` 分发到 `build_interpolation_transition()` 或 `build_bridge_transition()`。
3. bridge 模式的三段结构（pre + bridge + post）与架构文档 6.2 节一致。
   - `pre`: 从当前 RobotState 插值到 bridge_motion 的首帧。
   - `bridge`: 从 bridge_motion 中截取。
   - `post`: 从 bridge_motion 的运动学末帧插值到下一段目标入口帧。
4. transition 段的 `reference_frames` 构造完成后可被 `track()` 直接消费。

**签名必须与架构文档一致**：

```python
class TransitionBuilder:
    def __init__(self, motion_source, motion_adapter):
        ...

    def build_transition(self, transition_spec, current_state, next_skill_spec) -> ReferenceSegment:
        ...

    def build_interpolation_transition(self, spec, current_state, next_skill_spec) -> ReferenceSegment:
        ...

    def build_bridge_transition(self, spec, current_state, next_skill_spec) -> ReferenceSegment:
        ...
```

#### M3c：matcher

**关键指令**：

1. 第一版为静态匹配：使用 `SkillSpec` 中的 `motion_file` 和 `default_start_frame`。
2. `duration` 存在时按 `motion.fps` 计算 `end_frame`。
3. `robot_state` 参数保留但当前版本不使用。

**签名必须与架构文档一致**：

```python
class MotionMatcher:
    def select(self, robot_state, skill_spec, motion, duration=None) -> MatchResult:
        ...
```

#### M3d：root 重锚

**关键指令**：

1. 实现 `reanchor_reference_frames()`，支持两种模式。
2. 若 M0 结论为 absolute root → skill clip 和 transition target entry 都重锚到当前真实 root。
3. 若 M0 结论为 root relative / 速度量 → 函数存在但 pass-through。
4. mode 参数用于区分 "offset_root_pos" / "pass_through" 等模式。
5. `reanchor_yaw_only` 选项需可配置（来自 `configs/harness.yaml`）。

---

### M4：端到端集成

**关键指令**：

1. 实现 `HarnessOrchestrator`，串联 Task Plan → Middle Architecture → Low Level Execution。
2. 实现 `scripts/run_harness_sequence.py`，作为入口脚本。
3. 执行流程：
   ```text
   读取 SkillPlan
   for each skill in sequence:
     - matcher 确定 motion 和帧范围
     - slice 出 skill reference_frames
     - 如果有 transition spec:
         - 读取当前 RobotState
         - TransitionBuilder.build_transition 生成 transition reference_frames
         - runner.track(transition_frames)
     - runner.track(skill_frames)
     - 更新 RobotState
   ```
4. 执行日志和结果保存到 `outputs/`。
5. **不引入架构文档外的新文件。**

**签名必须与架构文档一致**：

```python
class HarnessOrchestrator:
    def __init__(self, runner, skill_registry, transition_registry, motion_adapter, config):
        ...

    def execute(self, skill_plan) -> list:  # list[ExecutionResult]
        ...
```

---

### M5：产物收敛

**关键指令**：

1. 运行 `Plan.md` M5 中的全量核验脚本。
2. 更新 `Documentation.md` 至最新状态。
3. 检查四份文档与 `Architecture_Desgin.md` 的一致性。
4. 如发现任何矛盾，修正文档（不修改架构文档）。

---

## 禁止事项清单

| 禁止行为 | 说明 |
|---------|------|
| 跳过 M0 | 任何 GMT 数值必须来自 M0 |
| 编造数值 | decimation、control_dt 等不可猜测 |
| 改名 | 架构文档里的模块名、类名、方法名一律不改 |
| 新增文件 | 不创建架构文档白名单外的 `.py` / `.yaml` 文件 |
| subprocess 调 sim2sim | 执行模型是 import runner，不是 subprocess |
| 段间 reset | 物理状态在 episode 内连续，track() 之间不 reset |
| 二选一写死 root 策略 | 两个分支都要实现，M0 后选定 |
| 离线拼大 pkl | 不在运行前拼接 motion 文件 |
| 重构已有模块 | 只增不改已有接口（除非 M0 结论强制要求修改） |
| 跳过 validation | 每个 milestone 先跑 validation，实现后再跑 |

---

## 文件总表（来自架构文档，禁止新增）

```text
HumaSkill/
├── task_plan/
│   ├── __init__.py
│   ├── skill_plan.py
│   └── skill_registry.py
├── middle_architecture/
│   ├── __init__.py
│   ├── gmt_motion_adapter.py
│   ├── reference_ops.py
│   ├── robot_state.py
│   ├── matcher.py
│   ├── transition_registry.py
│   ├── transition_builder.py
│   └── harness_orchestrator.py
├── low_level_execution/
│   ├── __init__.py
│   └── gmt_tracking_runner.py
├── configs/
│   ├── skills.yaml
│   ├── transitions.yaml
│   ├── harness.yaml
│   └── sequences/
│       └── demo_walk_kick_crouch_stand.yaml
├── scripts/
│   ├── inspect_gmt_motion_format.py
│   ├── inspect_gmt_obs_reference_contract.py
│   ├── run_harness_sequence.py
│   └── run_single_gmt_motion.py
├── assets/
│   └── motions/
│       ├── airkick_stand.pkl
│       ├── basic_walk.pkl
│       ├── crouchwalk_stand.pkl
│       ├── dance.pkl
│       ├── dance_waltz.pkl
│       ├── kick_walk.pkl
│       ├── squat.pkl
│       └── walk_stand.pkl
├── outputs/
│   └── contract/
│       └── GMT_obs_reference_contract.md
├── Architecture_Desgin.md
├── Prompt.md
├── Plan.md
├── Implement.md
└── Documentation.md
```

## GMT 路径

```yaml
gmt_root: G:/Code/Python/Paper-Reproduction/GMT/humanoid-general-motion-tracking
```

所有涉及 GMT 路径的代码使用此值作为默认值或从 `configs/harness.yaml` 读取。
