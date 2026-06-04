# 基于 GMT 的三层机器人动作执行 Harness 设计文档

## 0. 项目定位

本项目以 GMT（General Motion Tracking）作为底层通用动作追踪器，在其上构建一个面向机器人长序列动作执行的 harness。第一版只使用 GMT 项目中已经提供的 `.pkl` 动作文件，先打通从固定任务序列到同一 MuJoCo episode 内连续执行的完整链路。

GMT 的能力边界必须明确：

```text
GMT = sim2sim 测试环境
底层仿真 = MuJoCo
机器人 = Unitree G1
输入动作 = GMT 官方 pkl motion
输出效果 = 使用 pretrained tracking policy 在仿真中跟踪参考动作
```

GMT 当前只作为仿真验证环境使用。训练、数据处理、retarget、真机部署都属于 GMT 外部能力，第一版 harness 也只围绕 GMT 已有 sim2sim 能力进行架构封装。

当前可用 motion 文件限定为 GMT `assets/motions/` 中的 8 个真实 `.pkl`：

```text
airkick_stand.pkl
basic_walk.pkl
crouchwalk_stand.pkl
dance.pkl
dance_waltz.pkl
kick_walk.pkl
squat.pkl
walk_stand.pkl
```

其中，`crouch.pkl` 和 `stand_ready.pkl` 不在当前 GMT motion 资产中。需要稳定站立片段时使用 `walk_stand.pkl`，需要蹲走或蹲姿相关稳定片段时使用 `crouchwalk_stand.pkl`。

第一版固定任务：

```text
往前走 10s，然后踢腿，然后蹲下，然后站立
```

该任务对应的语义序列为：

```text
walk_forward, 10s
kick_leg
crouch_down
stand_up
```

第一版目标：

```text
YAML 固定动作序列
  ↓
Task Plan 层读取并检查 SkillPlan
  ↓
Middle Architecture 层按配置选择 GMT pkl，并在运行时生成衔接参考轨迹
  ↓
Low Level Execution 层在同一个 MuJoCo episode 中连续 track 多段参考轨迹
  ↓
每段执行后从活的 mujoco data 读取真实 RobotState
  ↓
输出每个 skill 和 transition 的执行结果
```

当前阶段重点：

```text
1. 三层工程结构清晰
2. 只使用 GMT 官方 8 个 pkl motion
3. 固定长序列任务可以在同一个 MuJoCo episode 内连续执行
4. 每段执行后使用真实 RobotState 生成下一段衔接参考轨迹
5. 先完成 GMT obs/reference 契约调查，再实现 runner 重构和 root 重锚
6. 后续再加入语言规划、复杂动态匹配、复杂失败恢复和自动 skill graph 搜索
```

平台风险说明：

```text
GMT 已在 Linux 和 M1 macOS 环境验证。
Windows 路径在 harness 配置中可以保留为开发风险项。
Windows 环境需要单独验证 MuJoCo、依赖库、路径格式和图形窗口行为。
```

---

## 1. 总体目录结构

建议项目根目录命名为：

```text
HumaSkill/
```

整体结构：

```text
HumaSkill/
├── task_plan/
├── middle_architecture/
├── low_level_execution/
├── configs/
├── scripts/
├── assets/
└── outputs/
```

三层含义：

```text
task_plan
任务规划层，负责把固定任务配置转成 SkillPlan。

middle_architecture
中层架构，负责把 SkillPlan 转成运行时可执行的 reference segment，并在线构造 transition。

low_level_execution
底层运动执行，负责封装 GMT runner，在同一个 MuJoCo episode 中连续 track reference frames。
```

`assets/` 第一版只保存或指向 GMT 官方 motion 文件：

```text
assets/motions/
├── airkick_stand.pkl
├── basic_walk.pkl
├── crouchwalk_stand.pkl
├── dance.pkl
├── dance_waltz.pkl
├── kick_walk.pkl
├── squat.pkl
└── walk_stand.pkl
```

---

## 2. 三层职责边界

### 2.1 Task Plan 层

第一版中，Task Plan 层只处理一个固定任务，用于打通三层 harness 的主链路。

当前任务定义为：

```text
往前走 10s，然后踢腿，然后蹲下，然后站立
```

该任务在 Task Plan 层被表示为一个结构化的 `SkillPlan`：

```yaml
task_id: demo_walk_kick_crouch_stand

sequence:
  - skill: walk_forward
    duration: 10.0

  - skill: kick_leg

  - skill: crouch_down

  - skill: stand_up
```

Task Plan 层的输出为：

```text
SkillPlan
```

其中，`SkillPlan` 本质上就是一个带有任务编号和动作顺序信息的 skill sequence。它只描述任务中需要依次执行哪些语义动作，以及少量任务级参数，例如 `duration`。

在当前任务中，Task Plan 层输出的 skill sequence 为：

```text
walk_forward, 10s
kick_leg
crouch_down
stand_up
```

Task Plan 层的职责边界为：

```text
固定任务配置
  ↓
读取 sequence
  ↓
检查 skill 是否存在于 registry
  ↓
生成 SkillPlan
  ↓
输出给 Middle Architecture 层
```

当前层只负责动作语义顺序，不负责 `.pkl` 文件选择，也不负责 transition reference frames 构造。具体某个 skill 对应哪个 GMT `.pkl` 文件，由 Middle Architecture 层根据动作库配置进行解析。

因此，Task Plan 层只需要保证输出的 `SkillPlan` 格式清晰、动作顺序明确，并保留必要的任务参数。

### 2.2 Middle Architecture 层

Middle Architecture 层接收 Task Plan 层输出的 `SkillPlan`，并依据其中的 skill sequence 驱动底层 GMT runner 按顺序执行。

输入为：

```text
SkillPlan
```

运行时输出为：

```text
ExecutionResult 列表
```

中层在运行过程中会生成：

```text
ReferenceFrames
ReferenceSegment
TransitionSpec
RobotState
```

其中，`ReferenceSegment` 是可以直接交给 GMT tracking policy 追踪的一段参考帧。它可以来自 GMT `.pkl` 的一段切片，也可以来自中层根据当前真实状态在线生成的 transition reference frames。

Middle Architecture 层的核心作用是：

```text
把语义动作序列转换成同一个 MuJoCo episode 内可连续执行的 reference segment 序列。
```

---

#### 2.2.1 通用处理流程

Middle Architecture 层依据接收到的 `SkillPlan` 逐步调度执行。`SkillPlan` 本身只描述任务语义顺序，中层负责把语义动作转换成具体的 GMT reference frames，并处理相邻动作之间的衔接关系。

整体流程为：

```text
接收 SkillPlan
  ↓
初始化 GMT runner
  ↓
读取当前真实 RobotState
  ↓
遍历 SkillPlan.sequence
  ↓
根据 skill_name 查询动作库配置
  ↓
读取对应 GMT pkl motion
  ↓
根据 duration 或 frame range 生成当前 skill reference frames
  ↓
根据 M0 契约结论决定 skill clip 是否需要 root 重锚
  ↓
根据静态 transition 配置生成上一段到当前段入口的衔接参考轨迹
  ↓
track(transition reference frames)
  ↓
从活的 mujoco data 读取真实 RobotState
  ↓
track(skill reference frames)
  ↓
从活的 mujoco data 读取真实 RobotState
  ↓
继续下一个 skill
```

组合轨迹在运行时按真实状态增量在线生成。第一版不把所有 motion 离线拼成一个大 `.pkl`，也不在每段之间重新启动 `sim2sim.py`。

---

#### 2.2.2 当前任务输入

当前 Task Plan 层输出的 `SkillPlan` 为：

```yaml
task_id: demo_walk_kick_crouch_stand

sequence:
  - skill: walk_forward
    duration: 10.0

  - skill: kick_leg

  - skill: crouch_down

  - skill: stand_up
```

该 `SkillPlan` 表示：

```text
walk_forward, 10s
kick_leg
crouch_down
stand_up
```

Middle Architecture 层会基于这个 skill sequence 生成并执行运行时 reference segment。

---

#### 2.2.3 动作库配置

当前只使用 GMT 项目中已有的 `.pkl` 动作片段。动作库配置用于描述每个 skill 对应的 motion 文件、默认帧范围和语义用途。

第一版统一使用这一套 skill schema：

```yaml
skills:
  <skill_name>:
    motion_file: <path_to_pkl>
    default_start_frame: <int>
    default_end_frame: <int | null>
    fps: 30.0
    description: <text>
```

字段含义：

```text
skill_name
语义动作名称，对应 SkillPlan.sequence 中的 skill 字段。

motion_file
该 skill 使用的 GMT pkl 文件路径。

default_start_frame
默认从 motion 的哪一帧开始取参考。

default_end_frame
默认取到哪一帧结束。null 表示取到 motion 末帧。

fps
参考动作采样率。GMT pkl 中 fps 约为 30.0。

description
给人看的动作说明。
```

当前固定任务需要的 skill registry 为：

```yaml
skills:
  walk_forward:
    motion_file: assets/motions/basic_walk.pkl
    default_start_frame: 0
    default_end_frame: null
    fps: 30.0
    description: forward walking reference. For 10s, use first 300 frames at 30fps.

  kick_leg:
    motion_file: assets/motions/airkick_stand.pkl
    default_start_frame: 0
    default_end_frame: null
    fps: 30.0
    description: standing air kick reference. Clip length must be confirmed in M0 or Step 1 before final demo.

  crouch_down:
    motion_file: assets/motions/squat.pkl
    default_start_frame: 0
    default_end_frame: null
    fps: 30.0
    description: squat or crouch-down reference. Clip length must be confirmed in M0 or Step 1 before final demo.

  stand_up:
    motion_file: assets/motions/walk_stand.pkl
    default_start_frame: 0
    default_end_frame: null
    fps: 30.0
    description: stable standing reference from walk_stand motion. Clip length must be confirmed in M0 or Step 1 before final demo.

  stable_stand_bridge:
    motion_file: assets/motions/walk_stand.pkl
    default_start_frame: 0
    default_end_frame: null
    fps: 30.0
    description: bridge reference used to return to a stable standing-like state.

  crouchwalk_bridge:
    motion_file: assets/motions/crouchwalk_stand.pkl
    default_start_frame: 0
    default_end_frame: null
    fps: 30.0
    description: bridge reference used around crouch-walk or crouch-related transitions.
```

在当前配置中：

```text
walk_forward 使用 basic_walk.pkl
kick_leg 使用 airkick_stand.pkl
crouch_down 使用 squat.pkl
stand_up 使用 walk_stand.pkl
stable_stand_bridge 使用 walk_stand.pkl
crouchwalk_bridge 使用 crouchwalk_stand.pkl
```

`basic_walk.pkl` 约 67 秒。当前任务中的 “往前走 10s” 按 30fps 截断为前 300 帧：

```text
start_frame = 0
end_frame = 300
```

这里采用 motion clip 截断，而不是循环播放。

`kick_leg`、`crouch_down`、`stand_up` 当前配置中的 `default_end_frame: null` 会播放整段 motion。例如 `airkick_stand.pkl` 可能达到约 26 秒。第一版实现时必须在 M0 或 Step 1 后确认各 clip 的真实长度，再为 demo 设置合适的 `default_end_frame`。文档此处只定义可调参数，不写死未经源码和数据核验的帧数。

---

#### 2.2.4 Motion Segment 构造

Middle Architecture 层会为 `SkillPlan.sequence` 中的每个 skill 生成一个 `ReferenceSegment`。该 segment 的本质是可以直接传给 GMT runner 的 `reference_frames`。

统一数据结构如下：

```python
from dataclasses import dataclass
from typing import Optional, Dict, Any
import numpy as np


@dataclass
class ReferenceFrames:
    fps: float
    root_pos: np.ndarray
    root_rot: np.ndarray
    dof_pos: np.ndarray
    local_body_pos: Optional[np.ndarray] = None


@dataclass
class ReferenceSegment:
    segment_id: str
    segment_type: str
    skill_name: Optional[str]
    reference_frames: ReferenceFrames
    source_motion_path: Optional[str] = None
    start_frame: Optional[int] = None
    end_frame: Optional[int] = None
    target_duration: Optional[float] = None
    transition_type: Optional[str] = None
    from_skill: Optional[str] = None
    to_skill: Optional[str] = None
    reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
```

其中：

```text
segment_type = skill
表示普通 skill 片段，reference_frames 来自 pkl motion 切片。

segment_type = transition
表示衔接片段，reference_frames 由 transition_builder 在运行时生成。

source_motion_path
记录参考帧来源。skill segment 通常来自某个 pkl；interpolation transition 可以为空；bridge transition 可以记录 bridge motion 来源。

reference_frames
底层 GMT runner 真正追踪的参考轨迹。
```

GMT pkl 格式固定为：

```text
dict {
  fps: float, 约 30.0
  root_pos: ndarray, shape = (N, 3)
  root_rot: ndarray, shape = (N, 4), quaternion order = wxyz
  dof_pos: ndarray, shape = (N, J)
  local_body_pos: ndarray, shape = (N, P, 3)
}
```

因此 motion 的起始状态和结束状态可以直接取第一帧和最后一帧：

```text
start_kin_state = frame[0]
end_kin_state = frame[-1]
```

对于带有 `duration` 的 skill，中层根据 fps 计算帧数。例如：

```yaml
sequence:
  - skill: walk_forward
    duration: 10.0
```

在 30fps 下生成：

```text
num_frames = round(10.0 * 30.0) = 300
start_frame = 0
end_frame = 300
motion_file = assets/motions/basic_walk.pkl
```

对应 `ReferenceSegment`：

```yaml
segment_id: skill_001_walk_forward
segment_type: skill
skill_name: walk_forward
source_motion_path: assets/motions/basic_walk.pkl
start_frame: 0
end_frame: 300
target_duration: 10.0
```

对于未指定 `duration` 的 skill，中层使用 motion 配置中的默认帧范围。如果 `default_end_frame: null`，则取到该 pkl 的末帧。正式 demo 前需要基于 M0 或 Step 1 的 motion 长度核验结果更新 `default_end_frame`。

例如：

```yaml
sequence:
  - skill: kick_leg
```

当前会转换为：

```yaml
segment_id: skill_002_kick_leg
segment_type: skill
skill_name: kick_leg
source_motion_path: assets/motions/airkick_stand.pkl
start_frame: 0
end_frame: null
target_duration: null
```

---

#### 2.2.5 动作衔接规则

由于 GMT 的每个 `.pkl` motion 是独立动作片段，相邻动作之间可能存在姿态、root 位姿和速度上的偏差。Middle Architecture 层需要在两个相邻 skill 之间构造 transition reference frames，并把 transition 当成普通参考轨迹交给同一个 tracking policy 去追踪。

第一版采用静态 transition 配置。固定任务的过渡点是已知的，因此每处衔接提前声明为 `interpolation` 或 `bridge`。第一版不依赖动态打分公式选择衔接方式。

当前固定任务包含三处衔接：

```text
walk_forward → kick_leg
kick_leg → crouch_down
crouch_down → stand_up
```

推荐第一版静态配置：

```yaml
transitions:
  - from_skill: walk_forward
    to_skill: kick_leg
    mode: bridge
    bridge_skill: stable_stand_bridge
    pre_bridge_interp_frames: 20
    post_bridge_interp_frames: 15
    reason: walking_to_standing_kick_needs_stable_stand_reference

  - from_skill: kick_leg
    to_skill: crouch_down
    mode: interpolation
    num_frames: 20
    reason: standing_kick_to_squat_uses_short_interpolation

  - from_skill: crouch_down
    to_skill: stand_up
    mode: interpolation
    num_frames: 20
    reason: squat_to_standing_uses_short_interpolation
```

`interpolation` transition 的生成逻辑：

```text
输入：
  current_state = 从活的 mujoco data 读取的真实 RobotState
  target_entry = 下一段 skill reference_frames 的第一帧
  num_frames = 配置指定帧数

生成：
  root_pos 使用 lerp
  root_rot 使用 slerp，四元数顺序保持 wxyz
  dof_pos 使用线性插值
  local_body_pos 可由两端 local_body_pos 线性插值，也可以在缺失时按目标帧填充或留空，具体取决于 M0 得到的 obs/reference 契约
```

关键约束：

```text
transition 第一帧接近机器人当前真实位姿。
transition 最后一帧接近下一段 reference 的入口帧。
transition 自身携带 reference_frames。
transition 通过同一个 GMTTrackingRunner.track(reference_frames) 执行。
```

pkl 中只包含位置参考，不直接包含速度参考。若 M0 结论显示 GMT observation 需要参考速度，则由 reference sequence 差分得到速度量。插值接缝处可能出现速度不连续，这一点需要和 obs/reference 契约一起处理，并作为第一版已知技术点记录。

`bridge` transition 的生成逻辑：

```text
输入：
  current_state = 当前真实 RobotState
  bridge_motion = walk_stand.pkl 或 crouchwalk_stand.pkl
  target_entry = 下一段 skill reference_frames 的第一帧

生成：
  part_1: current_state → bridge_motion 第一帧的 interpolation reference
  part_2: bridge_motion 的参考帧切片
  part_3: bridge_motion 末帧 → target_entry 的 interpolation reference
  concat(part_1, part_2, part_3) 得到一个 transition reference segment
```

注意：

```text
bridge transition 的 post 段从 bridge_motion 的运动学末帧插值到目标入口帧。
它不从执行 bridge 后的真实 RobotState 重新生成 post 段。
这是第一版为了保持 segment 构造简单而采用的刻意简化。
后续可改成 track(part_1 + part_2) 后读取真实 RobotState，再在线生成 post transition。
```

因此，bridge 不是一个只带 `motion_path` 的占位 segment。它在执行前已经被展开成真实 `reference_frames`，底层 runner 接收的仍然是：

```python
runner.track(reference_frames)
```

后续工作可以加入动态匹配和数值打分，例如：

```text
D = λq Dq + λroot Droot + λv Dv + λc Dc
```

其中：

```text
Dq 表示关节姿态差异
Droot 表示 root 位姿差异
Dv 表示速度差异
Dc 表示接触状态差异
```

这套打分公式只作为后续扩展方向，第一版固定任务不依赖它。

---

#### 2.2.6 root 重锚策略

当前版本只对 transition 按真实状态生成，而 skill clip 直接使用 pkl 原始帧。这一设计在 GMT obs/reference 契约确定前是不完整的。是否需要对 skill clip 做 root 重锚，必须由 M0 源码调查结论决定。

M0 需要回答：

```text
policy observation 中的参考目标是绝对 root，还是 root 相对量、速度量和 local_body_pos。
```

根据 M0 结论分两种情况处理。

情况 A：

```text
M0 结论：policy 跟踪绝对 root 或 observation 中显式使用绝对 root reference。
```

此时，skill clip 也必须重锚到当前真实 RobotState。重锚定义为：

```text
给定当前真实 RobotState 和原始 skill clip：
  1. 取 clip 首帧 root_pos 和 root_quat。
  2. 计算当前真实 root 与 clip 首帧 root 的平移差。
  3. 计算当前真实 yaw 与 clip 首帧 yaw 的差。
  4. 对整个 clip 的 root_pos 施加 yaw 旋转和平移，使 clip 首帧 root 与当前真实 root 对齐。
  5. 对整个 clip 的 root_rot 施加 yaw 对齐旋转，四元数顺序保持 wxyz。
  6. dof_pos 保持原 clip 关节轨迹。
  7. local_body_pos 是否旋转或保持局部坐标，按照 M0 obs/reference 契约决定。
```

此时，transition 的目标入口帧也必须使用重锚后的下一段 skill clip 第一帧，而不是 pkl 原始第一帧。

情况 B：

```text
M0 结论：policy 使用 root 相对量、速度量和 local_body_pos，绝对 root 轨迹不作为直接 tracking target。
```

此时，skill clip 可以保留 pkl 原始 root 参考，或只使用其相对位移、速度和局部身体目标。transition 仍按当前真实 RobotState 生成，但 reference_ops 中对 root_pos 的处理需要服从 M0 契约。

配置上使用：

```yaml
reference_contract:
  root_reference_mode: pending_m0
  reanchor_skill_clip: pending_m0
  reanchor_yaw_only: true
```

其中：

```text
root_reference_mode 可选值：
  pending_m0
  absolute_root
  root_relative

reanchor_skill_clip 可选值：
  pending_m0
  true
  false
```

在 M0 完成前，代码应拒绝进入正式长序列执行，或只允许以 `--allow-pending-contract` 方式进行开发 smoke test。

---

#### 2.2.7 当前任务生成的运行时 ReferenceSegment 序列

根据当前任务，Middle Architecture 层会在运行时逐步生成和执行如下 segment：

```yaml
task_id: demo_walk_kick_crouch_stand

runtime_segments:
  - segment_id: skill_001_walk_forward
    segment_type: skill
    skill_name: walk_forward
    source_motion_path: assets/motions/basic_walk.pkl
    start_frame: 0
    end_frame: 300
    target_duration: 10.0

  - segment_id: transition_001_walk_forward_to_kick_leg
    segment_type: transition
    transition_type: bridge
    from_skill: walk_forward
    to_skill: kick_leg
    bridge_skill: stable_stand_bridge
    source_motion_path: assets/motions/walk_stand.pkl
    carries_reference_frames: true
    reason: walking_to_standing_kick_needs_stable_stand_reference

  - segment_id: skill_002_kick_leg
    segment_type: skill
    skill_name: kick_leg
    source_motion_path: assets/motions/airkick_stand.pkl
    start_frame: 0
    end_frame: null

  - segment_id: transition_002_kick_leg_to_crouch_down
    segment_type: transition
    transition_type: interpolation
    from_skill: kick_leg
    to_skill: crouch_down
    num_frames: 20
    carries_reference_frames: true
    reason: standing_kick_to_squat_uses_short_interpolation

  - segment_id: skill_003_crouch_down
    segment_type: skill
    skill_name: crouch_down
    source_motion_path: assets/motions/squat.pkl
    start_frame: 0
    end_frame: null

  - segment_id: transition_003_crouch_down_to_stand_up
    segment_type: transition
    transition_type: interpolation
    from_skill: crouch_down
    to_skill: stand_up
    num_frames: 20
    carries_reference_frames: true
    reason: squat_to_standing_uses_short_interpolation

  - segment_id: skill_004_stand_up
    segment_type: skill
    skill_name: stand_up
    source_motion_path: assets/motions/walk_stand.pkl
    start_frame: 0
    end_frame: null
```

其中，`walk_forward` 的执行长度为 10 秒，按 30fps 取 `basic_walk.pkl` 的前 300 帧。由于 `basic_walk.pkl` 约 67 秒，该片段长度足够，直接截断即可。

相邻动作之间的 transition segment 由 Middle Architecture 层根据静态 transition 配置和当前真实 RobotState 在线生成。transition segment 在执行前已经携带完整 `reference_frames`，因此可以被底层 runner 直接追踪。

---

#### 2.2.8 当前版本的中层职责

当前版本中，Middle Architecture 层负责：

```text
读取 SkillPlan 中的 sequence
按顺序解析每个 skill step
根据 skill_name 查询 GMT pkl
读取 GMT pkl 的 fps、root_pos、root_rot、dof_pos、local_body_pos
为每个 skill 生成 reference frames
根据 M0 结论决定 skill clip 是否 root 重锚
从底层 executor 获取当前真实 RobotState
根据静态 transition 配置在线生成 transition reference frames
检查每个 motion_file 是否存在
检查 reference_frames shape 是否符合 GMT runner 输入要求
调用底层 executor 连续 track 每段 reference frames
每段结束后更新 RobotState
```

当前版本采用最小可运行的衔接逻辑：

```text
每个 skill 默认选择 registry 中声明的唯一 GMT pkl
每个 motion 默认从第 0 帧开始
walk_forward 按 10 秒截断为 basic_walk.pkl 前 300 帧
其余 skill clip 长度在 M0 或 Step 1 后通过 default_end_frame 调整
transition 使用静态配置声明 interpolation 或 bridge
transition 在线基于真实 RobotState 生成 reference frames
```

Middle Architecture 层的处理边界为：

```text
SkillPlan
  ↓
skill 到 pkl 的映射
  ↓
pkl 切片为 skill reference frames
  ↓
root 重锚条件处理
  ↓
真实 RobotState 到下一段入口的 transition reference frames
  ↓
连续调用 Low Level Execution 层
```

这一层负责把语义动作序列转换为可执行参考轨迹。GMT policy 的加载、仿真环境步进和真实状态读取由 Low Level Execution 层完成。

---

### 2.3 Low Level Execution 层

输入：

```text
ReferenceSegment
```

输出：

```text
ExecutionResult
```

这一层负责：

```text
初始化 GMT policy 和 MuJoCo 环境
维护同一个 MuJoCo episode
接收 reference_frames
调用 GMT tracking policy 执行 runner.track(reference_frames)
从活的 mujoco data 读取真实 RobotState
执行最小摔倒判定
返回 success、failed_reason、log_path、video_path、final_state 等结果
```

第一版必须把 GMT 原始 `sim2sim.py` 重构成可 import 的 runner。原版 `sim2sim.py` 的能力边界是单动作播放、跑完即退出。它没有连续执行、跨动作状态接力、loop 或 duration 开关。harness 的底层执行不能再用 `subprocess` 逐段调用原始 `sim2sim.py`，因为那会导致每段动作处于独立 episode，真实状态无法在动作之间传递。

底层 runner 暴露接口：

```text
initialize()
get_robot_state()
track(reference_frames)
```

推荐封装为：

```python
class GMTTrackingRunner:
    def initialize(self):
        ...

    def get_robot_state(self) -> RobotState:
        ...

    def track(self, reference_frames: ReferenceFrames) -> RunnerTrackResult:
        ...
```

同一个固定任务的执行过程必须保持同一个 MuJoCo model/data 和同一个 policy 实例：

```text
initialize()
  ↓
track(walk_forward_reference)
  ↓
get_robot_state()
  ↓
track(transition_reference)
  ↓
get_robot_state()
  ↓
track(kick_leg_reference)
  ↓
get_robot_state()
  ↓
...
```

多次 `track()` 之间保持物理状态连续，禁止在 segment 之间 reset episode。

---

## 3. 第一版 MVP 数据流

第一版完整流程：

```text
configs/sequences/demo_walk_kick_crouch_stand.yaml
  ↓
task_plan.sequence_loader 加载 YAML
  ↓
task_plan.skill_registry 检查 skill 定义
  ↓
task_plan.symbolic_planner 返回固定 SkillPlan
  ↓
middle_architecture.motion_source 查 motion pkl 路径
  ↓
middle_architecture.gmt_motion_adapter 读取 pkl 并提取 reference frames
  ↓
middle_architecture.matcher 选择 motion 文件和起始帧
  ↓
middle_architecture.reference_ops 切片、插值、拼接 reference frames
  ↓
middle_architecture.transition_registry 读取静态 transition 配置
  ↓
middle_architecture.transition_builder 根据真实 RobotState 在线生成 transition reference frames
  ↓
middle_architecture.segment_validator 检查 reference segment
  ↓
low_level_execution.gmt_executor 调用常驻 GMTTrackingRunner.track(reference_frames)
  ↓
low_level_execution.gmt_executor 从活的 mujoco data 读取 RobotState
  ↓
outputs/ 保存执行结果
```

第一版接受：

```text
固定任务
静态 transition 配置
只使用 GMT 官方 8 个 pkl
在同一个 MuJoCo episode 内顺序执行
每段结束后读取真实 RobotState
```

第一版需要先完成硬门槛：

```text
M0：GMT obs/reference 契约调查
```

M0 产出前，以下事项只能写成条件分支或配置项：

```text
runner 控制频率和物理频率
reference 时间索引方式
obs 中参考目标形式
skill clip 是否需要 root 重锚
local_body_pos 是否必须传入 policy observation
参考速度是否需要由差分生成
历史窗口和归一化状态如何维护
```

第一版暂缓：

```text
语言规划
复杂动态匹配
复杂失败恢复
离线大 pkl 拼接
跨 episode 的逐段 subprocess 调用
真机部署
训练或 retarget
```

后续再逐步加入：

```text
基于 RobotState 的入口帧搜索
基于 tracking error 的实时监控
基于 D 的 transition 类型自动选择
skill graph 搜索
LLM 输出结果校验
失败恢复计划
```

---

## 4. task_plan 文件夹设计

目录：

```text
task_plan/
├── schemas.py
├── skill_registry.py
├── sequence_loader.py
└── symbolic_planner.py
```

---

### 4.1 schemas.py

定义 Task Plan 层的数据结构。

```python
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SkillStep:
    skill: str
    duration: Optional[float] = None


@dataclass
class SkillPlan:
    task_id: str
    sequence: List[SkillStep]
```

`SkillStep.duration` 用于表达任务级时长需求。例如 `walk_forward` 的 `duration: 10.0` 表示希望使用 10 秒参考轨迹。中层会根据 motion fps 转换成帧范围。

---

### 4.2 skill_registry.py

管理 skill 与 GMT pkl 的映射关系。第一版只允许一套 `SkillSpec`，并且 YAML 字段与数据类字段保持一致。

```python
from dataclasses import dataclass
from typing import Dict, Optional
import yaml


@dataclass
class SkillSpec:
    name: str
    motion_file: str
    default_start_frame: int = 0
    default_end_frame: Optional[int] = None
    fps: float = 30.0
    description: str = ""


class SkillRegistry:
    def __init__(self, skills: Dict[str, SkillSpec]):
        self.skills = skills

    @classmethod
    def from_yaml(cls, path: str):
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        skills = {}

        for name, item in data["skills"].items():
            skills[name] = SkillSpec(
                name=name,
                motion_file=item["motion_file"],
                default_start_frame=int(item.get("default_start_frame", 0)),
                default_end_frame=item.get("default_end_frame"),
                fps=float(item.get("fps", 30.0)),
                description=item.get("description", ""),
            )

        return cls(skills)

    def get(self, name: str) -> SkillSpec:
        if name not in self.skills:
            raise KeyError(f"Unknown skill: {name}")
        return self.skills[name]

    def has(self, name: str) -> bool:
        return name in self.skills
```

当前 `configs/skills.yaml` 必须包含固定序列用到的全部 skill：

```text
walk_forward
kick_leg
crouch_down
stand_up
```

同时包含 transition 配置中用到的 bridge skill：

```text
stable_stand_bridge
crouchwalk_bridge
```

---

### 4.3 sequence_loader.py

从 YAML 文件读取动作序列。

```python
import yaml
from task_plan.schemas import SkillStep, SkillPlan


def load_skill_plan(path: str) -> SkillPlan:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    steps = []

    for item in data["sequence"]:
        steps.append(
            SkillStep(
                skill=item["skill"],
                duration=item.get("duration"),
            )
        )

    return SkillPlan(
        task_id=data.get("task_id", "unnamed_task"),
        sequence=steps,
    )
```

入口脚本统一加载：

```text
configs/sequences/demo_walk_kick_crouch_stand.yaml
```

---

### 4.4 symbolic_planner.py

第一版只做固定任务检查。它不自动插入未知 skill，也不基于 precondition/effect 做复杂修复。

```python
class SymbolicPlanner:
    def __init__(self, registry):
        self.registry = registry

    def validate(self, plan):
        for step in plan.sequence:
            self.registry.get(step.skill)
        return plan
```

后续可以加入：

```text
skill graph 搜索
precondition 检查
effect 状态更新
失败恢复计划
LLM 输出结果校验
```

---

## 5. middle_architecture 文件夹设计

目录：

```text
middle_architecture/
├── motion_source.py
├── gmt_motion_adapter.py
├── robot_state.py
├── matcher.py
├── reference_ops.py
├── transition_registry.py
├── transition_builder.py
├── segment_validator.py
├── scheduler.py
└── recovery.py
```

Middle Architecture 层负责将 Task Plan 层输出的 `SkillPlan` 转换为可执行参考轨迹，并在同一个 GMT 仿真环境中对多个 reference segment 进行连续调度。

这一层的输入是：

```text
SkillPlan
```

这一层运行过程中使用：

```text
ReferenceFrames
ReferenceSegment
TransitionSpec
RobotState
ExecutionResult
```

其中，`ReferenceSegment` 表示单个可执行参考片段，`RobotState` 表示从活的 MuJoCo data 中读取的真实机器人状态，`ExecutionResult` 用于记录每段执行结果。

Middle Architecture 层的核心流程为：

```text
接收 SkillPlan
  ↓
逐个读取 skill step
  ↓
根据 skill 名称查询 GMT pkl
  ↓
读取 GMT motion 基本信息
  ↓
根据 M0 结论处理 skill clip root 重锚
  ↓
根据当前 RobotState 和静态配置生成 transition reference frames
  ↓
在同一个 GMT 仿真环境中执行 transition
  ↓
读取真实 RobotState
  ↓
执行当前 skill reference frames
  ↓
读取真实 RobotState
  ↓
继续下一段
```

---

### 5.1 motion_source.py

`motion_source.py` 负责根据 skill 名称返回对应的 GMT `.pkl` 文件。

它只做动作来源查询，将语义层的 skill 名称映射到中层可以使用的 motion 文件路径。

示例：

```python
class MotionSource:
    def __init__(self, skill_registry):
        self.skill_registry = skill_registry

    def get_skill_spec(self, skill_name: str):
        return self.skill_registry.get(skill_name)

    def get_motion_file(self, skill_name: str) -> str:
        return self.skill_registry.get(skill_name).motion_file
```

对于当前任务：

```text
walk_forward → basic_walk.pkl
kick_leg → airkick_stand.pkl
crouch_down → squat.pkl
stand_up → walk_stand.pkl
stable_stand_bridge → walk_stand.pkl
crouchwalk_bridge → crouchwalk_stand.pkl
```

这一文件的职责边界为：

```text
skill_name
  ↓
SkillSpec
  ↓
GMT pkl 文件路径
```

---

### 5.2 gmt_motion_adapter.py

`gmt_motion_adapter.py` 负责读取 GMT `.pkl` motion，并将其包装成中层统一使用的 `GMTMotion` 对象。

GMT pkl 格式已经确定：

```text
dict {
  fps: float, 约 30.0
  root_pos: ndarray, shape = (N, 3)
  root_rot: ndarray, shape = (N, 4), quaternion order = wxyz
  dof_pos: ndarray, shape = (N, J)
  local_body_pos: ndarray, shape = (N, P, 3)
}
```

代码结构：

```python
from dataclasses import dataclass
from typing import Optional
import pickle
import numpy as np

from middle_architecture.robot_state import KinematicFrame


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

    def frame(self, index: int) -> KinematicFrame:
        return KinematicFrame(
            root_pos=self.root_pos[index].copy(),
            root_quat=self.root_rot[index].copy(),
            dof_pos=self.dof_pos[index].copy(),
            local_body_pos=None if self.local_body_pos is None else self.local_body_pos[index].copy(),
        )

    @property
    def start_frame(self) -> KinematicFrame:
        return self.frame(0)

    @property
    def end_frame(self) -> KinematicFrame:
        return self.frame(self.num_frames - 1)


def load_gmt_motion(path: str, name: str = "") -> GMTMotion:
    with open(path, "rb") as f:
        raw = pickle.load(f)

    required_keys = ["root_pos", "root_rot", "dof_pos"]

    for key in required_keys:
        if key not in raw:
            raise KeyError(f"GMT motion missing key: {key}")

    fps = float(raw.get("fps", 30.0))
    root_pos = raw["root_pos"]
    root_rot = raw["root_rot"]
    dof_pos = raw["dof_pos"]
    local_body_pos = raw.get("local_body_pos")

    num_frames = int(root_pos.shape[0])

    if root_rot.shape[0] != num_frames or dof_pos.shape[0] != num_frames:
        raise ValueError("GMT motion frame count mismatch.")

    if root_rot.shape[1] != 4:
        raise ValueError("root_rot must have shape (N, 4) with wxyz quaternion order.")

    return GMTMotion(
        name=name,
        path=path,
        fps=fps,
        root_pos=root_pos,
        root_rot=root_rot,
        dof_pos=dof_pos,
        local_body_pos=local_body_pos,
        num_frames=num_frames,
    )
```

这一文件的职责边界为：

```text
GMT pkl path
  ↓
GMTMotion
  ↓
motion frame slicing
  ↓
start/end kinematic frame extraction
```

---

### 5.3 robot_state.py

`robot_state.py` 用于定义同一个 GMT 仿真环境中的当前机器人真实状态。

每执行完一个 `ReferenceSegment`，系统都需要从 GMT runner 的活体 MuJoCo data 中读取当前状态，并将该状态返回给 Middle Architecture 层，用于下一段动作的入口衔接和后续匹配。

```python
from dataclasses import dataclass
from typing import Optional
import numpy as np


@dataclass
class KinematicFrame:
    root_pos: np.ndarray
    root_quat: np.ndarray
    dof_pos: np.ndarray
    local_body_pos: Optional[np.ndarray] = None


@dataclass
class RobotState:
    root_pos: np.ndarray
    root_quat: np.ndarray
    dof_pos: np.ndarray
    root_lin_vel: np.ndarray
    root_ang_vel: np.ndarray
    dof_vel: np.ndarray
```

从 MuJoCo freejoint 状态读取时，推荐封装在底层 runner 中：

```python
def read_robot_state_from_mujoco(data, num_dof: int) -> RobotState:
    root_pos = data.qpos[0:3].copy()
    root_quat = data.qpos[3:7].copy()
    dof_pos = data.qpos[7:7 + num_dof].copy()

    root_lin_vel = data.qvel[0:3].copy()
    root_ang_vel = data.qvel[3:6].copy()
    dof_vel = data.qvel[6:6 + num_dof].copy()

    return RobotState(
        root_pos=root_pos,
        root_quat=root_quat,
        dof_pos=dof_pos,
        root_lin_vel=root_lin_vel,
        root_ang_vel=root_ang_vel,
        dof_vel=dof_vel,
    )
```

当前任务中的状态流转为：

```text
执行 walk_forward reference
  ↓
读取真实 RobotState
  ↓
用真实 RobotState 生成 walk_forward 到 kick_leg 的 transition reference
  ↓
执行 transition reference
  ↓
读取真实 RobotState
  ↓
执行 kick_leg reference
  ↓
继续处理 crouch_down 和 stand_up
```

这一文件的职责边界为：

```text
活的 MuJoCo data
  ↓
RobotState
```

`RobotState` 是 Middle Architecture 层与 Low Level Execution 层之间的真实状态接口。它在 matcher、reference_ops 和 transition_builder 中被实际使用。

---

### 5.4 matcher.py

`matcher.py` 负责根据当前 `RobotState` 和候选 motion，选择当前 skill 对应的具体 GMT `.pkl` 文件和起始帧。

第一版采用最小逻辑：

```text
使用 SkillSpec 中声明的唯一 motion_file
默认从 SkillSpec.default_start_frame 开始
duration 存在时根据 fps 截断帧数
```

但是接口保留 `robot_state`，这样当前版本可以在同一个仿真环境中连续执行，后续也可以直接扩展成状态匹配。

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class MatchResult:
    motion_path: str
    start_frame: int
    end_frame: Optional[int]
    score: float
    reason: str


class MotionMatcher:
    def select(self, robot_state, skill_spec, motion, duration=None):
        start_frame = skill_spec.default_start_frame

        if duration is not None:
            num_frames = int(round(float(duration) * float(motion.fps)))
            end_frame = min(start_frame + num_frames, motion.num_frames)
        else:
            end_frame = skill_spec.default_end_frame

        if end_frame is None:
            end_frame = motion.num_frames

        return MatchResult(
            motion_path=skill_spec.motion_file,
            start_frame=start_frame,
            end_frame=end_frame,
            score=0.0,
            reason="static_first_version_match",
        )
```

对于 `basic_walk.pkl`：

```text
motion duration ≈ 67s
fps ≈ 30.0
duration = 10.0
end_frame = 300
```

后续匹配逻辑可以基于：

```text
当前 RobotState
  ↓
候选 motion 的所有帧
  ↓
计算状态偏差
  ↓
选择最合适的 motion_path 和 start_frame
```

状态偏差可作为后续扩展：

```text
D = λq Dq + λroot Droot + λv Dv + λc Dc
```

这一文件的职责边界为：

```text
RobotState + SkillSpec + GMTMotion
  ↓
MatchResult
```

---

### 5.5 reference_ops.py

`reference_ops.py` 负责 reference frames 的基础操作。它被 `transition_builder.py` 调用，避免切片、插值、拼接逻辑散落在多个模块里。

该模块提供三个核心函数：

```python
slice_motion_to_reference_frames(motion, start_frame, end_frame) -> ReferenceFrames
interpolate_reference_frames(start, target_frame, num_frames, fps) -> ReferenceFrames
concat_reference_frames(list_of_reference_frames) -> ReferenceFrames
```

`slice_motion_to_reference_frames`：

```python
def slice_motion_to_reference_frames(motion, start_frame, end_frame):
    return ReferenceFrames(
        fps=motion.fps,
        root_pos=motion.root_pos[start_frame:end_frame].copy(),
        root_rot=motion.root_rot[start_frame:end_frame].copy(),
        dof_pos=motion.dof_pos[start_frame:end_frame].copy(),
        local_body_pos=None
        if motion.local_body_pos is None
        else motion.local_body_pos[start_frame:end_frame].copy(),
    )
```

`interpolate_reference_frames` 必须同时接受 `RobotState` 和 `KinematicFrame` 作为起点。实现时先统一转成 kinematic 视图：

```python
def _as_kinematic_view(x):
    if isinstance(x, RobotState):
        return KinematicFrame(
            root_pos=x.root_pos,
            root_quat=x.root_quat,
            dof_pos=x.dof_pos,
            local_body_pos=None,
        )

    if isinstance(x, KinematicFrame):
        return x

    raise TypeError(f"Unsupported kinematic input type: {type(x)}")
```

插值接口：

```python
def interpolate_reference_frames(start, target_frame, num_frames, fps):
    start_frame = _as_kinematic_view(start)
    target = _as_kinematic_view(target_frame)

    root_pos = lerp_sequence(
        start=start_frame.root_pos,
        target=target.root_pos,
        num_frames=num_frames,
    )

    root_rot = slerp_sequence_wxyz(
        start=start_frame.root_quat,
        target=target.root_quat,
        num_frames=num_frames,
    )

    dof_pos = lerp_sequence(
        start=start_frame.dof_pos,
        target=target.dof_pos,
        num_frames=num_frames,
    )

    local_body_pos = resolve_local_body_pos_for_interpolation(
        start=start_frame.local_body_pos,
        target=target.local_body_pos,
        num_frames=num_frames,
    )

    return ReferenceFrames(
        fps=fps,
        root_pos=root_pos,
        root_rot=root_rot,
        dof_pos=dof_pos,
        local_body_pos=local_body_pos,
    )
```

插值规则：

```text
dof_pos 使用线性插值。
root_pos 使用 lerp。
root_rot 使用 slerp，四元数顺序为 wxyz。
local_body_pos 两端都存在时可以线性插值。
local_body_pos 缺失时可以按目标帧填充，也可以留空，具体依赖 M0 obs/reference 契约。
```

若 M0 结论显示 observation 需要 `local_body_pos`，则 `resolve_local_body_pos_for_interpolation()` 需要保证输出 shape 与 GMT policy 预期一致。若 M0 结论显示 observation 不使用 `local_body_pos`，则可以留空。

`concat_reference_frames`：

```python
def concat_reference_frames(list_of_reference_frames):
    if len(list_of_reference_frames) == 0:
        raise ValueError("Cannot concat empty reference frame list.")

    fps = list_of_reference_frames[0].fps

    for frames in list_of_reference_frames:
        if abs(frames.fps - fps) > 1e-6:
            raise ValueError("Cannot concat reference frames with different fps.")

    root_pos = np.concatenate([x.root_pos for x in list_of_reference_frames], axis=0)
    root_rot = np.concatenate([x.root_rot for x in list_of_reference_frames], axis=0)
    dof_pos = np.concatenate([x.dof_pos for x in list_of_reference_frames], axis=0)

    if all(x.local_body_pos is not None for x in list_of_reference_frames):
        local_body_pos = np.concatenate([x.local_body_pos for x in list_of_reference_frames], axis=0)
    else:
        local_body_pos = None

    return ReferenceFrames(
        fps=fps,
        root_pos=root_pos,
        root_rot=root_rot,
        dof_pos=dof_pos,
        local_body_pos=local_body_pos,
    )
```

`root 重锚` 可作为该模块的扩展函数：

```python
def reanchor_reference_frames(reference_frames, current_state, mode):
    ...
```

该函数是否启用由 M0 结论决定。

---

### 5.6 transition_registry.py

`transition_registry.py` 负责读取 `configs/transitions.yaml`，并提供相邻 skill 的静态 transition spec 查询能力。

数据结构：

```python
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import yaml


@dataclass
class TransitionSpec:
    from_skill: str
    to_skill: str
    mode: str
    num_frames: Optional[int] = None
    bridge_skill: Optional[str] = None
    pre_bridge_interp_frames: Optional[int] = None
    post_bridge_interp_frames: Optional[int] = None
    reason: str = ""
```

注册表：

```python
class TransitionRegistry:
    def __init__(self, specs: Dict[Tuple[str, str], TransitionSpec]):
        self.specs = specs

    @classmethod
    def from_yaml(cls, path: str):
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        specs = {}

        for item in data.get("transitions", []):
            spec = TransitionSpec(
                from_skill=item["from_skill"],
                to_skill=item["to_skill"],
                mode=item["mode"],
                num_frames=item.get("num_frames"),
                bridge_skill=item.get("bridge_skill"),
                pre_bridge_interp_frames=item.get("pre_bridge_interp_frames"),
                post_bridge_interp_frames=item.get("post_bridge_interp_frames"),
                reason=item.get("reason", ""),
            )

            key = (spec.from_skill, spec.to_skill)

            if key in specs:
                raise ValueError(f"Duplicated transition spec: {key}")

            specs[key] = spec

        return cls(specs)

    def get(self, from_skill: str, to_skill: str) -> TransitionSpec:
        key = (from_skill, to_skill)

        if key not in self.specs:
            raise KeyError(
                f"Missing transition spec from {from_skill} to {to_skill}. "
                f"Please add it to configs/transitions.yaml."
            )

        return self.specs[key]
```

职责边界：

```text
configs/transitions.yaml
  ↓
TransitionSpec
  ↓
按 (from_skill, to_skill) 查询
```

第一版固定任务必须包含以下三条：

```text
walk_forward → kick_leg
kick_leg → crouch_down
crouch_down → stand_up
```

---

### 5.7 transition_builder.py

`transition_builder.py` 负责构造可执行参考片段，并处理相邻动作之间的衔接。

这一文件需要支持两类 transition：

```text
interpolation transition
用于固定配置声明为短时插值的衔接。

bridge transition
用于固定配置声明为插入稳定片段的衔接。
```

它依赖：

```text
MotionSource
MotionAdapter
reference_ops.slice_motion_to_reference_frames
reference_ops.interpolate_reference_frames
reference_ops.concat_reference_frames
```

构造函数必须和入口脚本保持一致：

```python
class TransitionBuilder:
    def __init__(self, motion_source, motion_adapter):
        self.motion_source = motion_source
        self.motion_adapter = motion_adapter
```

构造普通 skill reference segment：

```python
from middle_architecture.reference_ops import (
    slice_motion_to_reference_frames,
    interpolate_reference_frames,
    concat_reference_frames,
)


class TransitionBuilder:
    def __init__(self, motion_source, motion_adapter):
        self.motion_source = motion_source
        self.motion_adapter = motion_adapter

    def build_skill_segment(self, skill_name, motion, match_result, duration=None):
        frames = slice_motion_to_reference_frames(
            motion=motion,
            start_frame=match_result.start_frame,
            end_frame=match_result.end_frame,
        )

        return ReferenceSegment(
            segment_id=f"skill_{skill_name}",
            segment_type="skill",
            skill_name=skill_name,
            reference_frames=frames,
            source_motion_path=match_result.motion_path,
            start_frame=match_result.start_frame,
            end_frame=match_result.end_frame,
            target_duration=duration,
        )
```

分发方法 `build_transition()`：

```python
    def build_transition(self, transition_spec, current_state, next_skill_segment):
        target_entry_frame = reference_frames_first_kinematic_frame(
            next_skill_segment.reference_frames
        )

        if transition_spec.mode == "interpolation":
            return self.build_interpolation_transition(
                current_state=current_state,
                target_entry_frame=target_entry_frame,
                from_skill=transition_spec.from_skill,
                to_skill=transition_spec.to_skill,
                num_frames=transition_spec.num_frames,
                reason=transition_spec.reason,
            )

        if transition_spec.mode == "bridge":
            if transition_spec.bridge_skill is None:
                raise ValueError(
                    f"Bridge transition {transition_spec.from_skill} -> "
                    f"{transition_spec.to_skill} requires bridge_skill."
                )

            bridge_skill_spec = self.motion_source.get_skill_spec(
                transition_spec.bridge_skill
            )

            bridge_motion = self.motion_adapter.load(
                bridge_skill_spec.motion_file,
                name=transition_spec.bridge_skill,
            )

            return self.build_bridge_transition(
                current_state=current_state,
                bridge_motion=bridge_motion,
                target_entry_frame=target_entry_frame,
                from_skill=transition_spec.from_skill,
                to_skill=transition_spec.to_skill,
                pre_bridge_interp_frames=transition_spec.pre_bridge_interp_frames,
                post_bridge_interp_frames=transition_spec.post_bridge_interp_frames,
                reason=transition_spec.reason,
            )

        raise ValueError(
            f"Unsupported transition mode: {transition_spec.mode} "
            f"for {transition_spec.from_skill} -> {transition_spec.to_skill}"
        )
```

其中 `reference_frames_first_kinematic_frame()` 可以放在 `reference_ops.py`：

```python
def reference_frames_first_kinematic_frame(frames):
    return KinematicFrame(
        root_pos=frames.root_pos[0].copy(),
        root_quat=frames.root_rot[0].copy(),
        dof_pos=frames.dof_pos[0].copy(),
        local_body_pos=None
        if frames.local_body_pos is None
        else frames.local_body_pos[0].copy(),
    )
```

构造插值过渡：

```python
    def build_interpolation_transition(
        self,
        current_state,
        target_entry_frame,
        from_skill,
        to_skill,
        num_frames,
        reason,
    ):
        if num_frames is None or num_frames <= 0:
            raise ValueError("interpolation transition requires positive num_frames.")

        frames = interpolate_reference_frames(
            start=current_state,
            target_frame=target_entry_frame,
            num_frames=num_frames,
            fps=30.0,
        )

        return ReferenceSegment(
            segment_id=f"transition_{from_skill}_to_{to_skill}",
            segment_type="transition",
            skill_name=None,
            reference_frames=frames,
            transition_type="interpolation",
            from_skill=from_skill,
            to_skill=to_skill,
            reason=reason,
        )
```

构造 bridge transition：

```python
    def build_bridge_transition(
        self,
        current_state,
        bridge_motion,
        target_entry_frame,
        from_skill,
        to_skill,
        pre_bridge_interp_frames,
        post_bridge_interp_frames,
        reason,
    ):
        if pre_bridge_interp_frames is None or pre_bridge_interp_frames <= 0:
            raise ValueError("bridge transition requires positive pre_bridge_interp_frames.")

        if post_bridge_interp_frames is None or post_bridge_interp_frames <= 0:
            raise ValueError("bridge transition requires positive post_bridge_interp_frames.")

        pre = interpolate_reference_frames(
            start=current_state,
            target_frame=bridge_motion.start_frame,
            num_frames=pre_bridge_interp_frames,
            fps=bridge_motion.fps,
        )

        bridge = slice_motion_to_reference_frames(
            motion=bridge_motion,
            start_frame=0,
            end_frame=bridge_motion.num_frames,
        )

        post = interpolate_reference_frames(
            start=bridge_motion.end_frame,
            target_frame=target_entry_frame,
            num_frames=post_bridge_interp_frames,
            fps=bridge_motion.fps,
        )

        frames = concat_reference_frames([pre, bridge, post])

        return ReferenceSegment(
            segment_id=f"transition_{from_skill}_to_{to_skill}",
            segment_type="transition",
            skill_name=None,
            reference_frames=frames,
            source_motion_path=bridge_motion.path,
            transition_type="bridge",
            from_skill=from_skill,
            to_skill=to_skill,
            reason=reason,
        )
```

注意：

```text
post 段使用 bridge_motion.end_frame 作为起点。
post 段不读取执行完 bridge 后的真实 RobotState。
这是第一版的刻意简化，后续可以拆成 bridge 前半段执行、读取真实状态、再生成 post。
```

插值规则：

```text
dof_pos:
  linear interpolation

root_pos:
  lerp

root_rot:
  slerp, quaternion order = wxyz

local_body_pos:
  如果两端都有 local_body_pos，则线性插值。
  如果当前真实状态缺少 local_body_pos，则可在第一版中填充目标帧 local_body_pos 或交给 runner 内部 kinematics 处理。
  最终处理方式待 M0 源码调查确认。
```

这一文件的职责边界为：

```text
RobotState + next skill entry frame + static TransitionSpec
  ↓
transition ReferenceSegment
```

---

### 5.8 segment_validator.py

`segment_validator.py` 负责检查生成的 `ReferenceSegment` 是否可以交给底层执行。

当前版本至少检查：

```text
source motion path 是否存在
reference_frames 是否存在
root_pos、root_rot、dof_pos 帧数是否一致
root_rot 是否为 (N, 4)
dof_pos 是否为 (N, J)
fps 是否大于 0
skill duration 对应的帧数是否大于 0
transition 是否携带 reference_frames
M0 契约状态是否允许正式执行
```

示例：

```python
from pathlib import Path


class SegmentValidator:
    def __init__(self, require_m0_contract=True):
        self.require_m0_contract = require_m0_contract

    def validate(self, segment):
        if segment.source_motion_path is not None:
            self._validate_motion_path(segment.source_motion_path)

        frames = segment.reference_frames

        if frames is None:
            raise ValueError("ReferenceSegment requires reference_frames.")

        n = frames.root_pos.shape[0]

        if n <= 0:
            raise ValueError("reference_frames must contain at least one frame.")

        if frames.root_rot.shape[0] != n:
            raise ValueError("root_rot frame count mismatch.")

        if frames.dof_pos.shape[0] != n:
            raise ValueError("dof_pos frame count mismatch.")

        if frames.root_pos.shape[1] != 3:
            raise ValueError("root_pos must have shape (N, 3).")

        if frames.root_rot.shape[1] != 4:
            raise ValueError("root_rot must have shape (N, 4).")

        if frames.fps <= 0:
            raise ValueError(f"Invalid fps: {frames.fps}")

        return True

    def _validate_motion_path(self, motion_path):
        path = Path(motion_path)
        if not path.exists():
            raise FileNotFoundError(motion_path)
```

这一文件的职责边界为：

```text
ReferenceSegment
  ↓
合法性检查
```

---

### 5.9 scheduler.py

`scheduler.py` 是 Middle Architecture 层的主控调度器。

第一版应当在同一个 GMT 仿真环境中连续执行多个 segment，而不是每个 `.pkl` 单独启动一次仿真。因此，`scheduler.py` 需要持有一个已经初始化好的低层 executor，并通过它连续执行所有动作片段。

整体逻辑为：

```text
接收 SkillPlan
  ↓
executor.initialize()
  ↓
读取当前真实 RobotState
  ↓
按顺序处理每个 skill step
  ↓
为当前 skill 构造 skill reference segment
  ↓
根据 M0 结论决定是否重锚当前 skill reference segment
  ↓
若当前 skill 前面存在上一段，则根据静态 TransitionSpec 构造 transition reference segment
  ↓
executor.track(transition reference)
  ↓
读取真实 RobotState
  ↓
executor.track(skill reference)
  ↓
读取真实 RobotState
  ↓
继续处理下一个 skill
```

示例结构：

```python
class MiddleScheduler:
    def __init__(
        self,
        motion_source,
        motion_adapter,
        matcher,
        transition_builder,
        transition_registry,
        validator,
        executor,
        recovery_manager=None,
        reference_contract=None,
    ):
        self.motion_source = motion_source
        self.motion_adapter = motion_adapter
        self.matcher = matcher
        self.transition_builder = transition_builder
        self.transition_registry = transition_registry
        self.validator = validator
        self.executor = executor
        self.recovery_manager = recovery_manager
        self.reference_contract = reference_contract

    def run(self, skill_plan):
        self.executor.initialize()

        state = self.executor.get_robot_state()
        results = []
        previous_skill = None

        for step in skill_plan.sequence:
            skill_spec = self.motion_source.get_skill_spec(step.skill)
            motion = self.motion_adapter.load(skill_spec.motion_file, name=step.skill)

            match = self.matcher.select(
                robot_state=state,
                skill_spec=skill_spec,
                motion=motion,
                duration=step.duration,
            )

            skill_segment = self.transition_builder.build_skill_segment(
                skill_name=step.skill,
                motion=motion,
                match_result=match,
                duration=step.duration,
            )

            skill_segment = self._maybe_reanchor_skill_segment(
                segment=skill_segment,
                current_state=state,
            )

            self.validator.validate(skill_segment)

            if previous_skill is not None:
                transition_spec = self.transition_registry.get(previous_skill, step.skill)

                transition_segment = self.transition_builder.build_transition(
                    transition_spec=transition_spec,
                    current_state=state,
                    next_skill_segment=skill_segment,
                )

                self.validator.validate(transition_segment)

                transition_result = self.executor.execute_segment(transition_segment)
                results.append(transition_result)
                state = transition_result.final_state

                if not transition_result.success:
                    return self._handle_failure(transition_result, results)

            result = self.executor.execute_segment(skill_segment)
            results.append(result)
            state = result.final_state

            if not result.success:
                return self._handle_failure(result, results)

            previous_skill = step.skill

        return results

    def _maybe_reanchor_skill_segment(self, segment, current_state):
        if self.reference_contract is None:
            return segment

        if self.reference_contract.reanchor_skill_clip is True:
            segment.reference_frames = reanchor_reference_frames(
                reference_frames=segment.reference_frames,
                current_state=current_state,
                mode=self.reference_contract.root_reference_mode,
            )

        return segment

    def _handle_failure(self, result, results):
        if self.recovery_manager is None:
            return results

        recovery_segment = self.recovery_manager.handle_failure(
            result=result,
            current_state=self.executor.get_robot_state(),
        )

        if recovery_segment is None:
            return results

        self.validator.validate(recovery_segment)
        recovery_result = self.executor.execute_segment(recovery_segment)
        results.append(recovery_result)

        return results
```

这一文件的职责边界为：

```text
SkillPlan
  ↓
连续 reference segment 调度
  ↓
同一个 GMT 仿真环境中的连续执行
  ↓
ExecutionResult 列表
```

`scheduler.py` 是中层和底层之间的连接点。它不直接实现 GMT policy，也不直接改写仿真步进逻辑，而是通过 Low Level Execution 层提供的 executor 接口完成执行。

---

### 5.10 recovery.py

`recovery.py` 负责在执行失败时生成恢复参考轨迹。

第一版固定任务优先关注主链路，复杂失败恢复划入后续工作。当前文件可以保留最小接口，默认返回 `None`，也可以用 `walk_stand.pkl` 生成一个简单稳定参考。

示例：

```python
class RecoveryManager:
    def __init__(self, transition_builder, stable_motion):
        self.transition_builder = transition_builder
        self.stable_motion = stable_motion

    def handle_failure(self, result, current_state):
        return None
```

后续可以扩展为：

```text
根据当前真实 RobotState 生成回到 walk_stand 入口的 interpolation
track walk_stand 稳定片段
重新规划剩余 sequence
```

这一文件的职责边界为：

```text
ExecutionResult failure + RobotState
  ↓
recovery ReferenceSegment
```

---

### 5.11 当前版本中层总结

当前版本的 Middle Architecture 层需要满足：

```text
从 SkillPlan 读取动作顺序
根据 skill 查找 GMT pkl
读取 GMT motion 信息
根据 duration 截断 motion
根据 M0 结论决定 skill clip 是否 root 重锚
根据当前 RobotState 和静态 transition 配置生成衔接参考轨迹
transition 携带真实 reference_frames
在同一个 GMT executor 中连续执行所有 segment
每段执行后更新 RobotState
```

当前任务的执行链路为：

```text
walk_forward, 10s
  ↓
bridge transition using walk_stand
  ↓
kick_leg
  ↓
interpolation transition
  ↓
crouch_down
  ↓
interpolation transition
  ↓
stand_up
```

---

## 6. low_level_execution 文件夹设计

目录：

```text
low_level_execution/
├── execution_result.py
├── gmt_executor.py
├── gmt_runner.py
├── log_parser.py
└── video_recorder.py
```

第一版必须完成：

```text
execution_result.py
gmt_executor.py
gmt_runner.py
```

其中，`gmt_runner.py` 是对重构后 GMT sim2sim runner 的封装。原始 `sim2sim.py` 仍可作为单 motion smoke test 使用，但 harness 主链路使用可 import 的常驻 runner。

---

### 6.1 execution_result.py

定义底层返回结果。

```python
from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class ExecutionResult:
    segment_id: str
    segment_type: str
    skill_name: Optional[str]
    success: bool
    final_state: Optional[Any]
    num_frames: int
    source_motion_path: Optional[str] = None
    log_path: Optional[str] = None
    video_path: Optional[str] = None
    failed_reason: Optional[str] = None


@dataclass
class RunnerTrackResult:
    success: bool
    num_frames: int
    log_path: Optional[str] = None
    video_path: Optional[str] = None
    failed_reason: Optional[str] = None
```

---

### 6.2 gmt_executor.py

第一版使用常驻 runner，而不是 `subprocess` 调 GMT 原始 `sim2sim.py`。

设备默认值使用 `auto` 或 `cpu`。GMT 官方单机 CPU 也可以运行，因此文档不把 `cuda` 写成默认前提。

```python
from pathlib import Path

from low_level_execution.execution_result import ExecutionResult
from low_level_execution.gmt_runner import GMTTrackingRunner


class GMTExecutor:
    def __init__(
        self,
        gmt_root: str,
        robot: str = "g1",
        output_root: str = "outputs",
        device: str = "auto",
    ):
        self.gmt_root = Path(gmt_root)
        self.robot = robot
        self.output_root = Path(output_root)
        self.device = device
        self.runner = None

    def initialize(self):
        self.runner = GMTTrackingRunner(
            gmt_root=str(self.gmt_root),
            robot=self.robot,
            device=self.device,
        )
        self.runner.initialize()

    def get_robot_state(self):
        if self.runner is None:
            raise RuntimeError("GMTExecutor is not initialized.")
        return self.runner.get_robot_state()

    def execute_segment(self, segment):
        if self.runner is None:
            raise RuntimeError("GMTExecutor is not initialized.")

        try:
            result = self.runner.track(segment.reference_frames)
            final_state = self.runner.get_robot_state()

            return ExecutionResult(
                segment_id=segment.segment_id,
                segment_type=segment.segment_type,
                skill_name=segment.skill_name,
                success=result.success,
                final_state=final_state,
                num_frames=result.num_frames,
                source_motion_path=segment.source_motion_path,
                log_path=result.log_path,
                video_path=result.video_path,
                failed_reason=result.failed_reason,
            )

        except Exception as e:
            final_state = self.runner.get_robot_state()

            return ExecutionResult(
                segment_id=segment.segment_id,
                segment_type=segment.segment_type,
                skill_name=segment.skill_name,
                success=False,
                final_state=final_state,
                num_frames=0,
                source_motion_path=segment.source_motion_path,
                failed_reason=str(e),
            )
```

工程注意点：

```text
GMT 原始 sim2sim.py 默认是单动作播放和退出。
harness 需要把其中 policy 加载、env 初始化、motion tracking 主循环拆出来。
GMTTrackingRunner 在 initialize() 中加载一次模型和 MuJoCo 环境。
GMTTrackingRunner.track(reference_frames) 只推进当前活的 MuJoCo data。
GMTTrackingRunner.get_robot_state() 从当前 data.qpos 和 data.qvel 读取真实状态。
```

---

### 6.3 gmt_runner.py

`gmt_runner.py` 是对 GMT sim2sim 能力的可 import 封装。它可以放在 harness 内，也可以作为 GMT 仓库中 `sim2sim.py` 的重构结果被 harness import。

核心接口固定为：

```python
class GMTTrackingRunner:
    def initialize(self):
        ...

    def get_robot_state(self):
        ...

    def track(self, reference_frames):
        ...
```

设备选择：

```text
device = auto
  优先按 GMT 原项目和本机依赖自动选择。
  如果 GPU 不可用，则使用 CPU。
```

伪代码结构：

```python
class GMTTrackingRunner:
    def __init__(self, gmt_root, robot="g1", device="auto", fall_config=None):
        self.gmt_root = gmt_root
        self.robot = robot
        self.device = device
        self.fall_config = fall_config
        self.model = None
        self.data = None
        self.policy = None
        self.num_dof = None

        self.control_dt = None
        self.physics_dt = None
        self.decimation = None
        self.reference_fps = None
        self.obs_history = None
        self.obs_normalizer = None

    def initialize(self):
        self._load_mujoco_model()
        self._create_mujoco_data()
        self._load_tracking_policy()
        self._load_obs_normalizer_if_needed()
        self._initialize_obs_history_if_needed()
        self._initialize_robot_state()
        self._load_timing_contract_from_m0()

    def get_robot_state(self):
        return read_robot_state_from_mujoco(
            data=self.data,
            num_dof=self.num_dof,
        )

    def track(self, reference_frames):
        num_control_steps = self._compute_control_steps(reference_frames)

        for control_step in range(num_control_steps):
            ref = self._sample_reference_by_time(
                reference_frames=reference_frames,
                control_step=control_step,
            )

            obs = self._build_observation(ref)
            obs = self._normalize_observation_if_needed(obs)

            action = self.policy(obs)
            self._apply_action(action)

            for _ in range(self.decimation):
                self._step_mujoco_physics()

            if self._has_fallen():
                return RunnerTrackResult(
                    success=False,
                    num_frames=control_step,
                    log_path=None,
                    video_path=None,
                    failed_reason="fell",
                )

        return RunnerTrackResult(
            success=True,
            num_frames=num_control_steps,
            log_path=None,
            video_path=None,
            failed_reason=None,
        )
```

`track(reference_frames)` 的步进方式必须复刻 GMT 原始 `sim2sim.py`，包括：

```text
控制频率
物理频率
decimation
reference 30fps 到控制步的时间索引
reference 是否按时间插值采样
policy observation 是否包含历史窗口
observation normalization 的加载和更新方式
```

这些具体数值和实现细节均标注为：

```text
待 M0 源码调查确认
```

因此，文档不写死 “一个参考帧对应一个 mj_step”。runner 的真实实现需要以 `sim2sim.py` 为准。

最小摔倒判定：

```python
    def _has_fallen(self) -> bool:
        state = self.get_robot_state()

        root_height = state.root_pos[2]
        body_tilt = estimate_body_tilt_from_quat(state.root_quat)

        if root_height < self.fall_config.min_root_height:
            return True

        if body_tilt > self.fall_config.max_body_tilt:
            return True

        return False
```

阈值配置：

```yaml
fall_detection:
  enabled: true
  min_root_height: pending_m0_or_empirical_config
  max_body_tilt: pending_m0_or_empirical_config
```

摔倒判定最小要求：

```text
root 高度低于阈值时返回 success=False。
机身倾角过大时返回 success=False。
failed_reason 设置为 "fell"。
阈值先作为配置占位，M0 和 smoke test 后再填。
```

`track(reference_frames)` 的输入来自中层，包括普通 skill reference 和 transition reference。底层不需要区分它来自 `.pkl` 还是在线插值。

这一文件的职责边界为：

```text
GMT pretrained policy + MuJoCo data
  ↓
track(reference_frames)
  ↓
真实 RobotState
```

---

## 7. configs 文件夹设计

目录：

```text
configs/
├── skills.yaml
├── transitions.yaml
├── harness.yaml
└── sequences/
    └── demo_walk_kick_crouch_stand.yaml
```

---

### 7.1 configs/skills.yaml

```yaml
skills:
  walk_forward:
    motion_file: assets/motions/basic_walk.pkl
    default_start_frame: 0
    default_end_frame: null
    fps: 30.0
    description: forward walking reference. For 10s, use first 300 frames.

  kick_leg:
    motion_file: assets/motions/airkick_stand.pkl
    default_start_frame: 0
    default_end_frame: null
    fps: 30.0
    description: standing air kick reference. default_end_frame must be tuned after M0 or motion length inspection.

  crouch_down:
    motion_file: assets/motions/squat.pkl
    default_start_frame: 0
    default_end_frame: null
    fps: 30.0
    description: squat or crouch-down reference. default_end_frame must be tuned after M0 or motion length inspection.

  stand_up:
    motion_file: assets/motions/walk_stand.pkl
    default_start_frame: 0
    default_end_frame: null
    fps: 30.0
    description: stable standing reference from walk_stand motion. default_end_frame must be tuned after M0 or motion length inspection.

  stable_stand_bridge:
    motion_file: assets/motions/walk_stand.pkl
    default_start_frame: 0
    default_end_frame: null
    fps: 30.0
    description: stable bridge reference around standing entry.

  crouchwalk_bridge:
    motion_file: assets/motions/crouchwalk_stand.pkl
    default_start_frame: 0
    default_end_frame: null
    fps: 30.0
    description: bridge reference around crouch-walk or crouch-related entry.
```

---

### 7.2 configs/harness.yaml

```yaml
gmt:
  root: /path/to/humanoid-general-motion-tracking
  robot: g1
  device: auto

runtime:
  output_root: outputs
  stop_on_failure: true
  keep_single_episode: true
  require_m0_contract: true

motion_assets:
  root: assets/motions
  valid_motion_files:
    - airkick_stand.pkl
    - basic_walk.pkl
    - crouchwalk_stand.pkl
    - dance.pkl
    - dance_waltz.pkl
    - kick_walk.pkl
    - squat.pkl
    - walk_stand.pkl

middle_architecture:
  matcher: static_first_version
  transition: static_transition_config
  validator: reference_frames_shape_check

reference_contract:
  status: pending_m0
  root_reference_mode: pending_m0
  reanchor_skill_clip: pending_m0
  reanchor_yaw_only: true
  reference_velocity_policy: pending_m0
  local_body_pos_policy: pending_m0

runner_timing:
  control_dt: pending_m0
  physics_dt: pending_m0
  decimation: pending_m0
  reference_fps: 30.0
  reference_time_indexing: pending_m0
  obs_history: pending_m0
  obs_normalization: pending_m0

fall_detection:
  enabled: true
  min_root_height: pending_m0_or_empirical_config
  max_body_tilt: pending_m0_or_empirical_config

platform:
  verified:
    - linux
    - m1_macos
  windows_status: unverified
  windows_path_example: G:/Code/Python/Paper-Reproduction/GMT/humanoid-general-motion-tracking
  windows_risk_note: Windows path and runtime behavior require separate validation.
```

---

### 7.3 configs/sequences/demo_walk_kick_crouch_stand.yaml

```yaml
task_id: demo_walk_kick_crouch_stand

sequence:
  - skill: walk_forward
    duration: 10.0

  - skill: kick_leg

  - skill: crouch_down

  - skill: stand_up
```

该文件名是第一版唯一 demo sequence 文件名。正文、入口脚本和验收标准全部统一使用：

```text
configs/sequences/demo_walk_kick_crouch_stand.yaml
```

---

### 7.4 configs/transitions.yaml

```yaml
task_id: demo_walk_kick_crouch_stand

transitions:
  - from_skill: walk_forward
    to_skill: kick_leg
    mode: bridge
    bridge_skill: stable_stand_bridge
    pre_bridge_interp_frames: 20
    post_bridge_interp_frames: 15
    reason: walking_to_standing_kick_needs_stable_stand_reference

  - from_skill: kick_leg
    to_skill: crouch_down
    mode: interpolation
    num_frames: 20
    reason: standing_kick_to_squat_uses_short_interpolation

  - from_skill: crouch_down
    to_skill: stand_up
    mode: interpolation
    num_frames: 20
    reason: squat_to_standing_uses_short_interpolation
```

---

## 8. scripts 文件夹设计

目录：

```text
scripts/
├── inspect_gmt_motion_format.py
├── inspect_gmt_obs_reference_contract.py
├── run_harness_sequence.py
└── run_single_gmt_motion.py
```

---

### 8.1 inspect_gmt_motion_format.py

用于核验 GMT pkl 的内部字段。

```python
import pickle
import sys


def main():
    path = sys.argv[1]

    with open(path, "rb") as f:
        data = pickle.load(f)

    print("type:", type(data))

    if isinstance(data, dict):
        print("keys:", data.keys())
        for k, v in data.items():
            print(k, type(v), getattr(v, "shape", None), getattr(v, "dtype", None))
    else:
        print(data)


if __name__ == "__main__":
    main()
```

运行方式：

```bash
python scripts/inspect_gmt_motion_format.py assets/motions/walk_stand.pkl
```

预期格式：

```text
type: dict
keys include:
  fps
  root_pos
  root_rot
  dof_pos
  local_body_pos

root_pos: shape = (N, 3)
root_rot: shape = (N, 4), quaternion order = wxyz
dof_pos: shape = (N, J)
local_body_pos: shape = (N, P, 3)
fps: about 30.0
```

这一步的作用是核验本地文件与架构假设一致，并为 `gmt_motion_adapter.py` 的单元测试提供依据。

---

### 8.2 inspect_gmt_obs_reference_contract.py

该脚本用于完成 M0 契约调查，核心不是跑模型，而是辅助整理 GMT `sim2sim.py` 源码中的 obs/reference、控制频率、归一化和历史窗口契约。

脚本目标输出：

```text
outputs/contract/GMT_obs_reference_contract.md
```

文档至少回答：

```text
1. 如何只加载一次 policy + mujoco，并在不 reset 的前提下连续步进。
2. policy observation 的参考目标是绝对 root，还是 root 相对量、速度量和 local_body_pos。
3. skill clip 与 transition 是否需要重锚到当前真实 root。
4. 控制频率、物理频率、decimation 分别是什么。
5. 参考 30fps 如何按时间索引到控制步。
6. obs 是否带历史窗口。
7. obs normalization 如何加载和应用。
8. reference velocity 是否需要由参考序列差分得到。
9. local_body_pos 在 observation 中是否必需。
```

示例运行：

```bash
python scripts/inspect_gmt_obs_reference_contract.py \
  --gmt-root /path/to/humanoid-general-motion-tracking \
  --sim2sim sim2sim.py \
  --output outputs/contract/GMT_obs_reference_contract.md
```

该脚本可以包含源码搜索和人工检查提示，例如：

```text
搜索 observation 构造函数
搜索 motion_lib 取参考帧逻辑
搜索 policy 输入维度和 normalization
搜索 decimation、dt、control_dt、sim_dt
搜索 reset 调用位置
搜索 root_pos、root_rot、local_body_pos、dof_pos 在 obs 中的使用方式
```

M0 结论是 runner 重构、root 重锚、track 步进实现的前置条件。

---

### 8.3 run_harness_sequence.py

三层总入口。

```python
import yaml

from task_plan.sequence_loader import load_skill_plan
from task_plan.skill_registry import SkillRegistry
from task_plan.symbolic_planner import SymbolicPlanner

from middle_architecture.motion_source import MotionSource
from middle_architecture.gmt_motion_adapter import load_gmt_motion
from middle_architecture.matcher import MotionMatcher
from middle_architecture.transition_builder import TransitionBuilder
from middle_architecture.segment_validator import SegmentValidator
from middle_architecture.scheduler import MiddleScheduler
from middle_architecture.transition_registry import TransitionRegistry

from low_level_execution.gmt_executor import GMTExecutor


def load_harness_config(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class MotionAdapter:
    def load(self, path, name=""):
        return load_gmt_motion(path, name=name)


def main():
    config = load_harness_config("configs/harness.yaml")

    plan = load_skill_plan("configs/sequences/demo_walk_kick_crouch_stand.yaml")

    registry = SkillRegistry.from_yaml("configs/skills.yaml")

    symbolic_planner = SymbolicPlanner(registry)
    plan = symbolic_planner.validate(plan)

    motion_source = MotionSource(registry)
    motion_adapter = MotionAdapter()
    matcher = MotionMatcher()

    transition_builder = TransitionBuilder(
        motion_source=motion_source,
        motion_adapter=motion_adapter,
    )

    transition_registry = TransitionRegistry.from_yaml("configs/transitions.yaml")

    validator = SegmentValidator(
        require_m0_contract=config["runtime"].get("require_m0_contract", True),
    )

    executor = GMTExecutor(
        gmt_root=config["gmt"]["root"],
        robot=config["gmt"].get("robot", "g1"),
        device=config["gmt"].get("device", "auto"),
        output_root=config["runtime"].get("output_root", "outputs"),
    )

    scheduler = MiddleScheduler(
        motion_source=motion_source,
        motion_adapter=motion_adapter,
        matcher=matcher,
        transition_builder=transition_builder,
        transition_registry=transition_registry,
        validator=validator,
        executor=executor,
        reference_contract=config.get("reference_contract"),
    )

    results = scheduler.run(plan)

    for result in results:
        print(
            result.segment_id,
            "success=",
            result.success,
            "failed_reason=",
            result.failed_reason,
        )


if __name__ == "__main__":
    main()
```

入口脚本中所有构造参数需要和模块定义保持一致：

```text
TransitionBuilder(motion_source, motion_adapter)
TransitionRegistry.from_yaml("configs/transitions.yaml")
SegmentValidator(require_m0_contract=...)
GMTExecutor(..., device="auto")
MiddleScheduler(..., transition_registry=..., reference_contract=...)
```

---

### 8.4 run_single_gmt_motion.py

该脚本用于 smoke test 一个 GMT motion 是否可以由原版 sim2sim 或重构 runner 正常执行。

示例命令：

```bash
python scripts/run_single_gmt_motion.py --motion assets/motions/walk_stand.pkl --robot g1
```

也可以直接在 GMT 仓库中使用原始命令验证单 motion：

```bash
cd /path/to/humanoid-general-motion-tracking
python sim2sim.py --robot g1 --motion walk_stand.pkl
```

注意：

```text
GMT 官方命令使用 --motion。
原版 sim2sim.py 只适合单动作 smoke test。
harness 主链路使用 GMTTrackingRunner，不使用逐段 subprocess。
```

---

## 9. assets 文件夹设计

```text
assets/
├── motions/
└── README.md
```

第一版只放 GMT 已有 8 个 pkl：

```text
assets/motions/
├── airkick_stand.pkl
├── basic_walk.pkl
├── crouchwalk_stand.pkl
├── dance.pkl
├── dance_waltz.pkl
├── kick_walk.pkl
├── squat.pkl
└── walk_stand.pkl
```

建议保留一份说明：

```text
assets/README.md
```

内容：

```text
本目录保存 GMT 官方提供的 pkl motion 文件。
第一版 harness 只读取这些 pkl，不接入 TextOp、GMR 或其他 retarget motion。
可用 motion 文件固定为：
airkick_stand.pkl
basic_walk.pkl
crouchwalk_stand.pkl
dance.pkl
dance_waltz.pkl
kick_walk.pkl
squat.pkl
walk_stand.pkl
```

---

## 10. outputs 文件夹设计

建议每次运行保存到单独 task 目录。

```text
outputs/
├── contract/
│   └── GMT_obs_reference_contract.md
└── demo_walk_kick_crouch_stand/
    ├── run_summary.json
    ├── execution_log.json
    ├── skill_001_walk_forward/
    │   ├── result.json
    │   └── robot_state_final.npz
    ├── transition_001_walk_forward_to_kick_leg/
    │   ├── result.json
    │   └── robot_state_final.npz
    ├── skill_002_kick_leg/
    │   ├── result.json
    │   └── robot_state_final.npz
    ├── transition_002_kick_leg_to_crouch_down/
    │   ├── result.json
    │   └── robot_state_final.npz
    ├── skill_003_crouch_down/
    │   ├── result.json
    │   └── robot_state_final.npz
    ├── transition_003_crouch_down_to_stand_up/
    │   ├── result.json
    │   └── robot_state_final.npz
    └── skill_004_stand_up/
        ├── result.json
        └── robot_state_final.npz
```

后续可以加入：

```text
video.mp4
trajectory.npz
tracking_error.csv
reference_segments.npz
execution_log.json
```

---

## 11. 第一版开发顺序

### Step 1：核验 GMT pkl 格式

先运行：

```bash
python scripts/inspect_gmt_motion_format.py assets/motions/walk_stand.pkl
```

目标是核验 GMT 原有 `.pkl` motion 的内部结构：

```text
pkl 类型为 dict
字段包含 fps、root_pos、root_rot、dof_pos、local_body_pos
fps 约为 30.0
root_pos shape = (N, 3)
root_rot shape = (N, 4)，四元数顺序为 wxyz
dof_pos shape = (N, J)
local_body_pos shape = (N, P, 3)
motion 起始状态可以直接取第 0 帧
motion 结束状态可以直接取最后一帧
```

这一步还需要统计各 motion 的真实长度，尤其是：

```text
airkick_stand.pkl
squat.pkl
walk_stand.pkl
crouchwalk_stand.pkl
```

这些长度用于修订 `configs/skills.yaml` 中的 `default_end_frame`。当前 `default_end_frame: null` 只是开发初始值，正式 demo 前必须调整到合适片段。

---

### Step 2：确认 GMT 原始 motion 可以运行

先确认 GMT 原始命令可以正常执行一个已有 `.pkl`：

```bash
cd /path/to/humanoid-general-motion-tracking
python sim2sim.py --robot g1 --motion walk_stand.pkl
```

这一步只用于确认 GMT 环境、模型权重、机器人配置和原始 motion 文件可以正常运行。

工程风险：

```text
GMT 已在 Linux 和 M1 macOS 环境验证。
Windows 未验证。
如果使用 G:/Code/Python/... 这类 Windows 路径，需要单独验证路径、依赖和窗口渲染行为。
```

第一版 harness 的目标是连续执行多个动作片段，因此这一步只作为底层 GMT 可用性检查。真正的第一版执行链路需要在一个 GMT 仿真环境中加载一次 policy 和 env，然后连续执行多个 `ReferenceSegment`。

---

### Step M0：GMT obs/reference 契约调查

在重构 runner 前，必须先读 GMT `sim2sim.py` 源码并产出：

```text
outputs/contract/GMT_obs_reference_contract.md
```

该结论文档至少回答以下问题。

问题 A：

```text
如何只加载一次 policy + mujoco，并在不 reset 的前提下连续步进。
```

需要明确：

```text
policy 加载位置
MuJoCo model/data 创建位置
reset 调用位置
motion 加载位置
单 motion 结束后的退出逻辑
哪些部分可以移动到 initialize()
哪些部分应该留在 track(reference_frames)
```

问题 B：

```text
policy observation 的参考目标是绝对 root，还是 root 相对量、速度量和 local_body_pos。
```

该结论决定：

```text
skill clip 是否需要重锚到当前真实 root
transition 末帧目标是否使用重锚后的下一段入口帧
root_pos 和 root_rot 在 ReferenceFrames 中如何参与 obs
local_body_pos 是否必须传入 runner
```

文档不得在此处写死未经源码核实的答案。实现上需要支持条件分支：

```text
absolute_root:
  skill clip 需要 root 重锚。

root_relative:
  skill clip 可以保持相对参考或原始 root 轨迹。

pending_m0:
  阻止正式长序列执行。
```

问题 C：

```text
控制频率 vs 物理频率、参考 30fps 如何按时间索引、obs 是否带历史窗口与归一化。
```

需要明确：

```text
physics dt
control dt
decimation
一个 action 维持多少个 physics step
reference frame 如何由控制时间映射到 30fps motion
是否需要 reference 插值
obs 是否拼接历史窗口
normalizer 的加载路径和应用方式
```

后续 runner 重构、root 重锚、track 步进全部依赖 M0 结论。所有待源码确认的数值一律保留为配置项，不在设计文档中编造。

---

### Step 3：重构 GMT sim2sim runner

实现或改造：

```text
low_level_execution/gmt_runner.py
```

目标是把 GMT 原始 `sim2sim.py` 中的单动作执行逻辑拆成可 import 的 runner：

```text
GMTTrackingRunner.initialize()
GMTTrackingRunner.get_robot_state()
GMTTrackingRunner.track(reference_frames)
```

关键要求：

```text
initialize() 加载一次 MuJoCo model、data 和 tracking policy
track(reference_frames) 推进当前活的 MuJoCo episode
track() 内部步进复刻 sim2sim.py 的控制频率和物理频率
get_robot_state() 从当前 data.qpos 和 data.qvel 读取真实 RobotState
多次 track() 之间保持同一个物理状态
```

`track()` 中的控制/物理步进、参考时间索引、obs 历史窗口和归一化均待 M0 源码调查确认。

---

### Step 4：完成 Low Level Execution

实现：

```text
low_level_execution/execution_result.py
low_level_execution/gmt_executor.py
low_level_execution/gmt_runner.py
```

目标是提供一个连续执行接口：

```text
初始化 GMT policy 和仿真环境
接收 ReferenceSegment
在同一个 GMT env 中执行 reference_frames
每段执行后读取 RobotState
执行最小摔倒判定
返回每段 ExecutionResult
```

底层执行接口设计为：

```text
GMTExecutor.initialize()
GMTExecutor.get_robot_state()
GMTExecutor.execute_segment(segment)
```

这一层负责真正调用 GMT pretrained tracker，完成仿真环境步进、policy 推理、reference motion 跟踪、摔倒判定和状态回传。

---

### Step 5：完成 Task Plan

实现：

```text
task_plan/schemas.py
task_plan/skill_registry.py
task_plan/sequence_loader.py
task_plan/symbolic_planner.py
```

目标：

```text
读取当前固定任务配置
生成 SkillPlan
检查 skill registry 中存在所有 skill
输出 skill sequence
```

当前任务配置为：

```yaml
task_id: demo_walk_kick_crouch_stand

sequence:
  - skill: walk_forward
    duration: 10.0

  - skill: kick_leg

  - skill: crouch_down

  - skill: stand_up
```

Task Plan 层只输出语义动作序列：

```text
walk_forward, 10s
kick_leg
crouch_down
stand_up
```

这一层只负责 `SkillPlan` 的生成和检查。具体 skill 对应哪个 GMT `.pkl`，以及动作之间如何衔接，交给 Middle Architecture 层处理。

---

### Step 6：完成 Middle Architecture

实现：

```text
middle_architecture/motion_source.py
middle_architecture/gmt_motion_adapter.py
middle_architecture/robot_state.py
middle_architecture/matcher.py
middle_architecture/reference_ops.py
middle_architecture/transition_registry.py
middle_architecture/transition_builder.py
middle_architecture/segment_validator.py
middle_architecture/scheduler.py
middle_architecture/recovery.py
```

目标：

```text
接收 SkillPlan
根据 skill 查询 GMT pkl
读取 motion 基本信息
根据 duration 和 fps 生成 skill reference frames
按 M0 结论决定 skill clip 是否 root 重锚
通过 TransitionRegistry 读取 transition spec
通过 TransitionBuilder.build_transition() 生成 transition reference frames
transition 作为 reference_frames 交给同一个 tracking policy 执行
连续调用 Low Level Execution 层
```

当前任务对应的语义动作序列为：

```text
walk_forward, 10s
kick_leg
crouch_down
stand_up
```

Middle Architecture 层会将其转换为运行时 reference segment 序列。例如：

```text
walk_forward skill reference
bridge transition reference
kick_leg skill reference
interpolation transition reference
crouch_down skill reference
interpolation transition reference
stand_up skill reference
```

---

### Step 7：跑通总入口

运行：

```bash
python scripts/run_harness_sequence.py
```

该脚本需要串起三层：

```text
Task Plan 层读取当前任务配置
  ↓
输出 SkillPlan
  ↓
Middle Architecture 层生成第一段 skill reference
  ↓
Low Level Execution 层初始化 GMT env 和 policy
  ↓
在同一个仿真环境中执行 skill reference
  ↓
读取真实 RobotState
  ↓
Middle Architecture 层在线生成 transition reference
  ↓
Low Level Execution 层继续执行 transition reference
  ↓
重复直到任务结束
  ↓
保存执行日志和每段 ExecutionResult
```

目标输出示例：

```text
task_id=demo_walk_kick_crouch_stand

segment_001 skill_001_walk_forward success=True
segment_002 transition_001_walk_forward_to_kick_leg success=True
segment_003 skill_002_kick_leg success=True
segment_004 transition_002_kick_leg_to_crouch_down success=True
segment_005 skill_003_crouch_down success=True
segment_006 transition_003_crouch_down_to_stand_up success=True
segment_007 skill_004_stand_up success=True
```

如果机器人摔倒，输出示例：

```text
segment_004 transition_002_kick_leg_to_crouch_down success=False failed_reason=fell
```

---

## 12. 第一版实现范围

第一版只处理当前固定任务：

```text
往前走 10s，然后踢腿，然后蹲下，然后站立
```

第一版输入为：

```text
configs/sequences/demo_walk_kick_crouch_stand.yaml
```

第一版使用 GMT 项目中已有的 `.pkl` motion：

```text
airkick_stand.pkl
basic_walk.pkl
crouchwalk_stand.pkl
dance.pkl
dance_waltz.pkl
kick_walk.pkl
squat.pkl
walk_stand.pkl
```

固定任务实际使用：

```text
basic_walk.pkl
airkick_stand.pkl
squat.pkl
walk_stand.pkl
```

transition bridge 可使用：

```text
walk_stand.pkl
crouchwalk_stand.pkl
```

第一版需要完成的能力为：

```text
Task Plan 层输出 SkillPlan
Middle Architecture 层将 SkillPlan 转换为运行时 ReferenceSegment
TransitionRegistry 从 configs/transitions.yaml 查询静态衔接配置
reference_ops 提供 reference 切片、插值和拼接
TransitionBuilder.build_transition() 根据 transition mode 分发生成 reference frames
Middle Architecture 层基于真实 RobotState 在线生成 transition reference frames
Low Level Execution 层在同一个 GMT env 中连续执行所有 reference segment
每个 segment 执行后更新 RobotState
runner 按 M0 结论复刻 sim2sim.py 的控制和物理步进
runner 具备最小摔倒判定
执行结果保存到 outputs
```

第一版的动作衔接规则为：

```text
固定任务的每处衔接由 configs/transitions.yaml 静态声明
mode = interpolation 时在线生成插值 reference frames
mode = bridge 时使用 walk_stand 或 crouchwalk_stand 生成 bridge reference frames
transition 自身携带 reference_frames
transition 交给同一个 tracking policy 执行
```

第一版的 root 处理规则为：

```text
待 M0 源码调查确认。
若 obs 使用 absolute root，则 skill clip 和 transition target entry 都需要 root 重锚。
若 obs 使用 root relative 或速度量，则 skill clip 可保持相对参考。
```

第一版暂缓范围：

```text
语言规划
复杂动态匹配
复杂失败恢复
自动 skill graph 搜索
基于 D 的动态衔接评分
离线拼接一个大 pkl
逐段 subprocess 调用 sim2sim.py
训练、数据处理、retarget 和真机部署
```

---

## 13. 项目一句话描述

```text
本项目构建一个基于 GMT 的三层机器人动作执行 harness。Task Plan 层负责将当前固定任务转化为 SkillPlan，Middle Architecture 层负责将 SkillPlan 转换为可执行 reference segment，并基于真实 RobotState 在线生成动作衔接参考轨迹，Low Level Execution 层复用 GMT pretrained tracker，在同一个 MuJoCo 仿真 episode 中连续执行多个 GMT pkl motion segment。第一版只使用 GMT 项目中已有的 8 个 pkl 动作文件，并以 M0 obs/reference 契约调查作为 runner 重构、root 重锚和 track 步进实现的硬门槛，优先打通“往前走 10s，然后踢腿，然后蹲下，然后站立”这一固定任务的完整执行链路。
```

---

## 14. 第一版验收标准

第一版完成后，至少满足：

```text
1. 可以读取 configs/sequences/demo_walk_kick_crouch_stand.yaml。
2. Task Plan 层可以输出 SkillPlan。
3. configs/skills.yaml 包含 walk_forward、kick_leg、crouch_down、stand_up、stable_stand_bridge、crouchwalk_bridge。
4. assets/motions/ 中只依赖 GMT 真实存在的 8 个 pkl。
5. Step M0 已产出 outputs/contract/GMT_obs_reference_contract.md。
6. M0 结论明确 obs/reference 中 root 是 absolute_root 还是 root_relative。
7. root 重锚策略已按 M0 结论落地。
8. Middle Architecture 层可以根据 SkillPlan 查询 GMT pkl。
9. gmt_motion_adapter.py 可以读取 fps、root_pos、root_rot、dof_pos、local_body_pos。
10. gmt_motion_adapter.py 可以直接提取 motion 起始帧和结束帧。
11. walk_forward 可以从 basic_walk.pkl 截断出前 300 帧作为 10 秒参考。
12. kick_leg、crouch_down、stand_up 的 default_end_frame 已根据 motion 长度核验结果设置或明确保留为整段测试。
13. middle_architecture/reference_ops.py 已实现 slice_motion_to_reference_frames()。
14. middle_architecture/reference_ops.py 已实现 interpolate_reference_frames()，并同时支持 RobotState 和 KinematicFrame 起点。
15. middle_architecture/reference_ops.py 已实现 concat_reference_frames()。
16. middle_architecture/transition_registry.py 已实现 TransitionRegistry.from_yaml()。
17. TransitionRegistry 内部以 (from_skill, to_skill) 为键保存 TransitionSpec。
18. TransitionRegistry.get(from_skill, to_skill) 找不到配置时会抛出明确异常。
19. TransitionBuilder.__init__(motion_source, motion_adapter) 与入口脚本构造参数一致。
20. TransitionBuilder.build_transition() 已实现 mode 分发。
21. build_transition() 在 interpolation 模式下调用 build_interpolation_transition()。
22. build_transition() 在 bridge 模式下通过 bridge_skill 加载 bridge_motion 并调用 build_bridge_transition()。
23. Middle Architecture 层可以为每个 skill 生成 ReferenceSegment。
24. Middle Architecture 层可以根据 configs/transitions.yaml 生成 transition ReferenceSegment。
25. interpolation transition 的第一帧接近当前真实 RobotState，最后一帧接近下一段入口帧。
26. bridge transition 使用 walk_stand.pkl 或 crouchwalk_stand.pkl 生成真实 reference frames。
27. bridge transition 的 post 段第一版从 bridge_motion 运动学末帧插值到目标入口帧，并在文档中记录为已知局限。
28. transition segment 携带 reference_frames，底层可以直接 track。
29. Low Level Execution 层可以初始化一次 GMT env 和 policy。
30. Low Level Execution 层可以在同一个 GMT env 中连续执行所有 segment。
31. 多次 track() 之间保持同一个 MuJoCo data 和物理状态。
32. track() 步进方式与 sim2sim.py 的控制频率、物理频率、decimation 和参考时间索引一致。
33. 每次 track() 后可以从活的 mujoco data 读取 RobotState。
34. RobotState 至少包含 root_pos、root_quat、dof_pos、root_lin_vel、root_ang_vel、dof_vel。
35. 摔倒判定可以在 root 高度过低或机身倾角过大时触发 success=False。
36. 摔倒时 failed_reason 为 "fell"。
37. outputs 中可以保存当前任务的执行日志和每段结果。
38. scripts/run_harness_sequence.py 的 import、构造参数和模块方法签名全部能串通。
```

第一版展示效果：

```text
输入：
configs/sequences/demo_walk_kick_crouch_stand.yaml

任务：
往前走 10s，然后踢腿，然后蹲下，然后站立

输出：
机器人在同一个 GMT MuJoCo 仿真 episode 中连续完成多个 GMT pkl reference segment，并在相邻动作之间通过在线生成的 transition reference frames 完成基础衔接。runner 的控制频率、物理步进、reference 时间索引、root 重锚策略和 obs 契约均由 M0 源码调查结论驱动。
```
