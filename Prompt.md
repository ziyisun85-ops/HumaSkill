# Prompt — HumaSkill 第一版交付

## 目标

在 GMT（General Motion Tracking）sim2sim 环境之上，构建一个三层机器人动作执行 harness。第一版只使用 GMT 项目中已有的 8 个 `.pkl` 动作文件，打通从固定任务序列到**同一个 MuJoCo episode 内连续执行**的完整链路。

具体任务：

```text
往前走 10s，然后踢腿，然后蹲下，然后站立
```

对应语义序列：

```text
walk_forward(10s) → kick_leg → crouch_down → stand_up
```

三层结构：

```text
Task Plan 层       → 读取 YAML 任务配置，产出 SkillPlan
Middle Architecture 层 → 按 SkillPlan 查询 GMT pkl，在线生成 skill reference + transition reference
Low Level Execution 层 → 在同一个 MuJoCo episode 中连续 track 多段 reference frames
```

最终效果：

```text
输入：configs/sequences/demo_walk_kick_crouch_stand.yaml
输出：机器人在同一个 GMT MuJoCo 仿真 episode 中连续完成多个 GMT pkl reference segment，
      并在相邻动作之间通过在线生成的 transition reference frames 完成基础衔接。
      runner 的控制频率、物理步进、reference 时间索引、root 重锚策略和 obs 契约
      均由 M0 源码调查结论驱动。
```

---

## 非目标

以下明确不在第一版范围内：

- 语言规划（自然语言→任务序列）
- 复杂动态匹配（基于 RobotState 的多候选 motion 评分选择）
- 基于 D 数值的衔接质量打分
- 复杂失败恢复（摔倒后尝试其他路径）
- 离线拼接一个大的 pkl 文件
- 逐段 subprocess 调用 `sim2sim.py`
- 自动 skill graph 搜索
- 训练 policy、retarget 动作数据、真机部署
- 仿真视频录制（不作为硬性交付物；主链路跑通后可录 demo 视频作为展示材料）

---

## 硬约束

### 执行模型

```text
常驻单 MuJoCo episode + 真实状态闭环顺序执行。
使用可 import 的 GMTTrackingRunner（initialize / get_robot_state / track）。
段间不 reset 物理状态；禁止逐段 subprocess 调 sim2sim.py。
每段执行后从活的 mujoco data 读取真实 RobotState，用于生成下一段 transition。
```

### 数据与动作

```text
只用 GMT 官方 assets/motions/ 中的 8 个真实 pkl：
  airkick_stand.pkl, basic_walk.pkl, crouchwalk_stand.pkl,
  dance.pkl, dance_waltz.pkl, kick_walk.pkl, squat.pkl, walk_stand.pkl

第一版固定任务：walk_forward(10s) → kick_leg → crouch_down → stand_up
不新增、不重命名 pkl 文件。
```

### Transition 设计

```text
transition 本身是一条可被同一 tracking policy 追踪的 reference 轨迹。
interpolation 按真实 RobotState 在线生成（lerp + slerp）。
bridge 展开为 pre(插值) + bridge(来自 pkl) + post(插值到目标入口帧) 的真实 reference_frames。
具体衔接模式由 configs/transitions.yaml 静态声明。
```

### Root 重锚

```text
依赖 M0 结论的条件分支（不得二选一写死）：
  若 obs 跟踪绝对 root → skill clip 与 transition target entry 都重锚到当前真实 root。
  若 obs 为 root 相对/速度量 → 可不重锚。
两种分支都要在文档和代码中体现，M0 结论产出后选定分支落地。
```

### M0 硬门槛

```text
在实现任何 runner 重构、track 步进或 root 重锚之前，必须先完成 M0：
阅读 sim2sim.py 源码，产出《GMT obs/reference 契约结论》。
M0 不过，不准往下做 M1 及之后任何 milestone。
```

### 不引入文档外文件

```text
所有文件必须属于架构文档 Architecture_Desgin.md 中已列出的模块、配置和脚本。
不新增架构文档里不存在的 .py 模块、.yaml 配置文件或 scripts/ 脚本。
```

### 不编造 GMT 事实

```text
所有 GMT 相关数值（控制频率、物理频率、decimation、obs 归一化、历史窗口、
参考时间索引方式、local_body_pos 是否必需、参考速度量来源等）一律取自 M0 结论。
文档中不确定处统一标注"待 M0 源码调查确认"，不得编造数值或断言。
```

### 平台

```text
GMT 已在 Linux 和 M1 macOS 环境验证。
Windows 路径作为当前开发路径使用，GMT 官方验证环境仍以 Linux / M1 macOS 为准。
Windows 环境下的 MuJoCo、依赖库、路径格式和图形窗口行为单独标注为风险项。
```

### 成功判定

```text
episode 跑完且全程未触发摔倒判据即为成功。
track() 内含最小摔倒判定：root 高度低于阈值或机身倾角超过阈值 → success=False, failed_reason="fell"。
阈值先作为配置占位（pending_m0_or_empirical_config），M0 和 smoke test 后再填。
```

---

## 交付物

四个 Markdown 文件，交给 Codex 执行实现：

| 文件 | 用途 |
|------|------|
| `Prompt.md` | 本文件 — 目标、非目标、硬约束、Done When |
| `Plan.md` | 有序 milestone，每项带 acceptance criteria 和可执行的 validation commands |
| `Implement.md` | 给 Codex 的执行规则 — milestone 顺序、门禁、diff 纪律、GMT 取值来源 |
| `Documentation.md` | 活文档 — 当前状态/进度、关键决策、运行指南、已知局限与风险 |

注意：这四个文件本身**不是实现代码**。实现由 Codex 根据这四个文件和 `Architecture_Desgin.md` 完成。

---

## Done When（可验证的完成定义）

以下条件全部满足时，第一版交付完成。条件编号沿用 `Architecture_Desgin.md` 第 14 节的验收标准。

### 配置与资产

1. 可以读取 `configs/sequences/demo_walk_kick_crouch_stand.yaml`。
2. `configs/skills.yaml` 包含 `walk_forward`、`kick_leg`、`crouch_down`、`stand_up`、`stable_stand_bridge`、`crouchwalk_bridge`。
3. `assets/motions/` 中只依赖 GMT 真实存在的 8 个 pkl。

### M0 契约

4. Step M0 已产出 `outputs/contract/GMT_obs_reference_contract.md`。
5. M0 结论明确 obs/reference 中 root 是 `absolute_root` 还是 `root_relative`。
6. root 重锚策略已按 M0 结论落地（两种分支均实现，M0 后选定）。

### Task Plan 层

7. Task Plan 层可以输出 `SkillPlan`。

### Middle Architecture 层 — Motion 读取与切分

8. Middle Architecture 层可以根据 `SkillPlan` 查询 GMT pkl。
9. `gmt_motion_adapter.py` 可以读取 `fps`、`root_pos`、`root_rot`、`dof_pos`、`local_body_pos`。
10. `gmt_motion_adapter.py` 可以直接提取 motion 起始帧和结束帧（`get_kinematic_frame`）。
11. `walk_forward` 可以从 `basic_walk.pkl` 截断出前 300 帧作为 10 秒参考。
12. `kick_leg`、`crouch_down`、`stand_up` 的 `default_end_frame` 已根据 motion 长度核验结果设置或明确保留为整段测试。

### Middle Architecture 层 — Reference 操作

13. `reference_ops.py` 已实现 `slice_motion_to_reference_frames()`。
14. `reference_ops.py` 已实现 `interpolate_reference_frames()`，并同时支持 `RobotState` 和 `KinematicFrame` 起点。
15. `reference_ops.py` 已实现 `concat_reference_frames()`。
16. root 重锚函数 `reanchor_reference_frames()` 已实现，启用与否由 M0 结论决定。

### Middle Architecture 层 — Transition

17. `transition_registry.py` 已实现 `TransitionRegistry.from_yaml()`。
18. `TransitionRegistry` 内部以 `(from_skill, to_skill)` 为键保存 `TransitionSpec`。
19. `TransitionRegistry.get(from_skill, to_skill)` 找不到配置时抛出明确异常。
20. `TransitionBuilder.__init__(motion_source, motion_adapter)` 与入口脚本构造参数一致。
21. `TransitionBuilder.build_transition()` 已实现 mode 分发。
22. `build_transition()` 在 `interpolation` 模式下调用 `build_interpolation_transition()`。
23. `build_transition()` 在 `bridge` 模式下通过 `bridge_skill` 加载 bridge_motion 并调用 `build_bridge_transition()`。
24. Middle Architecture 层可以为每个 skill 生成 `ReferenceSegment`。
25. Middle Architecture 层可以根据 `configs/transitions.yaml` 生成 transition `ReferenceSegment`。
26. interpolation transition 的第一帧接近当前真实 `RobotState`，最后一帧接近下一段入口帧。
27. bridge transition 使用 `walk_stand.pkl` 或 `crouchwalk_stand.pkl` 生成真实 reference frames。
28. bridge transition 的 post 段从 bridge_motion 运动学末帧插值到目标入口帧（此简化在文档中记录为已知局限）。
29. transition segment 携带 `reference_frames`，底层可以直接 `track()`。

### Low Level Execution 层

30. 可以初始化一次 GMT env 和 policy（`GMTTrackingRunner.initialize()`）。
31. 可以在同一个 GMT env 中连续执行所有 segment（`track()` 多次调用，不 reset）。
32. 多次 `track()` 之间保持同一个 MuJoCo data 和物理状态。
33. `track()` 步进方式与 `sim2sim.py` 的控制频率、物理频率、decimation 和参考时间索引一致（具体数值取自 M0 结论）。
34. 每次 `track()` 后可以从活的 mujoco data 读取 `RobotState`。
35. `RobotState` 至少包含 `root_pos`、`root_quat`、`dof_pos`、`root_lin_vel`、`root_ang_vel`、`dof_vel`。
36. 摔倒判定在 root 高度过低或机身倾角过大时触发 `success=False`。
37. 摔倒时 `failed_reason` 为 `"fell"`。

### 集成与输出

38. `outputs/` 中可以保存当前任务的执行日志和每段结果。
39. `scripts/run_harness_sequence.py` 的 import、构造参数和模块方法签名全部能串通。
40. 端到端运行 `run_harness_sequence.py` 可在单 episode 内完成完整固定序列。
