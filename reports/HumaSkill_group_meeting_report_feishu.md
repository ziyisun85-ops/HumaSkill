# HumaSkill 项目阶段性汇报

## 1. 项目背景

已有的人形机器人动作生成模型或技能策略，通常可以完成单段动作；但高层语言任务往往包含多个连续动作。直接生成长程动作容易出现衔接不稳、状态漂移、失败后难恢复等问题。

HumaSkill 的目标，是把长程语言动作任务拆成可组合、可检查、可修复、可恢复的 skill sequence。

## 2. HumaSkill 的总体定位

HumaSkill 是一个 **skill-level composition and execution harness**。  
它位于底层动作生成模型或技能策略之上，负责：

- skill sequence 生成
- 序列校验
- 衔接修复
- 执行监控
- 失败恢复

它暂时不替代 TextOp，也不重新训练所有技能策略。

```text
Language Goal
↓
Composer
↓
Raw Skill Sequence
↓
Sequence Validator
↓
Transition Manager
↓
Repaired Skill Sequence
↓
Skill Executor
↓
Backend
↓
ExecutionResult
↓
Logs and Summary
```

## 3. 当前系统框架

### 3.1 模块职责

| 模块 | 职责 |
|---|---|
| `composer` | 语言到 skill sequence |
| `skills` | skill 元信息与注册 |
| `harness` | 校验、修复、执行、恢复 |
| `backends` | skill 执行接口 |
| `policies` | 预训练策略预留接口 |
| `logging_utils` | 日志与 summary |
| `utils` | 通用工具 |

### 3.2 关键接口

- `SkillInfo`：定义 skill contract
- `ExecutionResult`：统一 backend 返回结构
- `Backend interface`：统一执行接口
- `Policy interface`：后续策略接入接口
- `Transition repair`：基于姿态与风险的衔接修复
- `Recovery handling`：执行失败后的恢复处理

## 4. 已完成工作

### 4.1 HumaSkill MVP

HumaSkill 上层 MVP 已完成，目前已实现：

- `RuleBasedComposer`
- `SkillRegistry`
- `SequenceValidator`
- `TransitionManager`
- `DummyBackend`
- `SkillExecutor`
- `ExecutionResult`
- Logging and Summary
- pytest tests
- GitHub baseline

当前 dummy pipeline 已可运行：

```text
语言指令
→ skill sequence
→ transition repair
→ dummy backend execution
→ logs and summary
```

测试状态：当前仓库 `pytest -q` 为 **57 passed**。

`Codex App final review`：待确认。

### 4.2 G1 模型与动作数据准备

已完成：

- 已下载 Unitree G1 MuJoCo model
- 已下载 `openhe/g1-retargeted-motions`
- 已发现 **174** 个 `.pkl` motion files

已确认关键字段：

- `dof [T, 23]`：23 个关节自由度轨迹
- `root_trans_offset [T, 3]`：根节点位置
- `root_rot [T, 4]`：根节点旋转四元数

### 4.3 23 维 dof 动作片段转换

已生成：

- `motions/stand_ready.npy`
- `motions/arm_wave.npy`
- `motions/final_pose.npy`
- `motions/metadata.json`

这些文件目前是 **23 维关节 dof 轨迹**，还不是完整 MuJoCo `qpos` 片段。

### 4.4 G1 23-DoF 模型匹配

此前模型：

| 模型 | `nq` | `nv` | `nu` |
|---|---:|---:|---:|
| `model/unitree_g1/scene.xml` | 36 | 35 | 0 |

匹配模型：

| 模型 | `nq` | `nv` | `nu` |
|---|---:|---:|---:|
| `model/g1_description/g1_23dof.xml` | 30 | 29 | 23 |

匹配原因：

```text
root_trans_offset [3] + root_rot [4] + dof [23] = qpos [30]
```

## 5. 当前项目推进状态

当前项目进展可以概括为：

- HumaSkill 上层框架已经完成
- G1 动作数据检查与 23 维 dof 提取已经完成
- 已找到匹配的 23-DoF MuJoCo 模型

同时，从当前仓库文件可见，项目已经进一步进入 Task 08B 阶段，已存在：

- `motions/metadata_qpos.json`
- qpos 转换脚本
- qpos playback 测试脚本

因此，当前状态更准确地说是：**已经从上层 harness MVP 推进到 motion clip backend 接入前的验证阶段。**

## 6. 后续工作计划

### 6.1 短期工作

- 继续确认 `root_trans_offset + root_rot + dof` 到 30-D `qpos` 的转换结果
- 使用 `g1_23dof.xml` 做 MuJoCo qpos playback
- 检查动作是否可稳定加载与播放

### 6.2 中期工作

- 实现 `MotionClipMujocoBackend`
- 将 `skill_name` 映射到对应 qpos motion clips
- 让 `SkillExecutor` 调用 MuJoCo backend
- 返回结构化 `ExecutionResult`

### 6.3 后续 TextOp 接入

- 先使用已有 motion clips 作为 backend 资源
- 再检查 TextOp 输出格式
- 后续实现 `TextOpMujocoBackend`

整体分工：

- HumaSkill 负责高层 skill composition
- TextOp 提供 motion generation / motion policy
- MuJoCo 负责仿真执行

## 7. 面向 AAAI 的研究思路

该项目后续可以发展为一项面向语言引导 humanoid 长程动作执行的 skill-level framework。

潜在贡献点包括：

### 7.1 Skill contract

将每个 skill 表示为带有时长范围、起止姿态、风险等级、backend 元信息和执行接口的可组合单元。

### 7.2 Transition-aware repair

利用 `start_pose`、`end_pose` 和 `risk` 自动插入稳定过渡动作。

### 7.3 ExecutionResult-based recovery

利用结构化 backend 反馈支持失败检测、日志记录和恢复决策。

潜在论文标题：

**HumaSkill: Transition-Aware Skill Composition for Language-Guided Humanoid Motion Execution**

## 8. 后续实验设计

建议 baseline：

- Direct TextOp
- Fixed Skill Chain
- HumaSkill without Transition Repair
- HumaSkill full

建议指标：

- 任务完成率
- 动作切换失败率
- 失稳率
- 恢复成功率
- 执行时长误差
- 动作多样性

## 9. 当前风险与待解决问题

- qpos playback 不等于完整动力学控制
- `nu=23` 对齐后，actuator control mode 仍需检查
- 动作视觉质量仍需验证
- `MotionClipMujocoBackend` 尚未实现
- TextOp 输出格式尚未接入
- 若要形成论文，还需要更多任务、baseline 和定量实验

## 10. 下一步任务

下一步立即任务：

- Task 08B：继续确认 30-D qpos npy clips，并完成 MuJoCo qpos playback smoke test 的结果验收

随后任务：

- Task 09：实现 `MotionClipMujocoBackend`

再之后：

- 扩展动作库，开始 baseline 实验
