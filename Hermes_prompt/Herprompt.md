# HumaSkill 阶段一任务：项目规划、接口规范、任务拆分与 Agent Prompt 生成

你是 HumaSkill 项目的编排、规划和审查 agent。

你当前只执行阶段一任务。

阶段一目标：

创建项目管理文档、接口规范文档、任务拆分文档、开发顺序文档、验收清单、测试计划，以及后续给 coding agent 使用的子任务 prompt。

当前阶段重点是规划、接口固定、任务拆分和 prompt 生成。完整代码实现由后续 coding agent 按照生成的任务 prompt 完成。

你可以创建规划文件和任务 prompt 文件。你可以定义最终架构和文件结构。核心业务逻辑留给后续实现任务完成。

---

## 1. 项目名称与定位

项目名称：

```text
HumaSkill
```

Python package 名称：

```text
humaskill
```

项目英文定位：

```text
HumaSkill is a skill-level composition and execution harness for language-guided humanoid motion composition.
```

项目中文定位：

```text
HumaSkill 是一个面向语言引导人形机器人动作组合的技能级执行框架。
```

第一版 MVP 场景：

```text
用户输入：“跳一段 12 秒的欢快机器人舞蹈”
```

第一版 MVP 系统流程：

```text
语言指令
↓
技能序列生成
↓
序列校验
↓
动作衔接修复
↓
Dummy backend 执行
↓
failed 后触发 recover
↓
执行日志
↓
统计结果
```

第一版只实现 DummyBackend。

后续预留扩展：

```text
LLM composer
Motion clip backend
Trained skill policy backend
MuJoCo / Gym backend
Isaac Lab backend
TextOp backend
GR00T backend
Real humanoid robot backend
```

近期目标主要是仿真测试，尤其是 MuJoCo 或 Gym 风格环境。项目需要为已经训练好的 skill policy 预留接口，例如 `.pt`、`.pth`、`.pkl`、`.npz` 等策略文件。真实人形机器人执行属于远期扩展。

---

## 2. 阶段一必须创建的文件

请创建如下文件和目录：

```text
HumaSkill/
  PROJECT_PLAN.md
  INTERFACES.md
  TASKS.md
  AGENT_ASSIGNMENTS.md
  DEVELOPMENT_ORDER.md
  ACCEPTANCE_CHECKLIST.md
  TEST_PLAN.md

  agent_prompts/
    01_skeleton_prompt.md
    02_skills_registry_prompt.md
    03_composer_prompt.md
    04_transition_prompt.md
    05_backend_executor_prompt.md
    06_main_readme_testfix_prompt.md
    07_codex_app_final_review_prompt.md
```

这些文件将作为后续所有 coding agent 的共同契约。

---

## 3. 最终项目结构

所有规划文档和子任务 prompt 都必须基于以下最终项目结构：

```text
HumaSkill/
  README.md
  requirements.txt
  pyproject.toml
  .gitignore

  configs/
    skills.yaml
    default_config.yaml

  humaskill/
    __init__.py
    main.py

    composer/
      __init__.py
      base_composer.py
      rule_based_composer.py
      llm_composer.py

    skills/
      __init__.py
      skill_info.py
      skill_registry.py
      skill_schema.py

    harness/
      __init__.py
      transition_manager.py
      skill_executor.py
      safety_supervisor.py
      sequence_validator.py

    backends/
      __init__.py
      base_backend.py
      dummy_backend.py
      motion_clip_backend.py
      trained_policy_backend.py
      mujoco_gym_backend.py
      isaaclab_backend.py
      textop_backend.py
      groot_backend.py

    policies/
      __init__.py
      base_policy.py
      policy_registry.py
      policy_adapter.py
      checkpoint_loader.py

    logging_utils/
      __init__.py
      execution_logger.py
      summary.py

    utils/
      __init__.py
      io.py
      math_utils.py
      printing.py
      errors.py

  scripts/
    run_demo.py
    validate_skills.py

  examples/
    demo_dance_request.json
    demo_raw_sequence.json
    demo_repaired_sequence.json

  logs/
    .gitkeep

  tests/
    __init__.py
    test_composer.py
    test_skill_registry.py
    test_transition_manager.py
    test_executor.py
    test_backend.py
```

---

## 4. PROJECT_PLAN.md 要求

创建 `PROJECT_PLAN.md`。

文件中必须包含以下部分。

### 4.1 项目目标

说明 HumaSkill 第一版目标：

```text
将自然语言目标转换为 humanoid skill sequence，并通过 transition repair、execution monitoring 和 recovery handling 提高动作序列的可执行性。
```

### 4.2 系统流程

包含如下流程：

```text
User Text
↓
Composer Agent
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
Execution Logs
↓
Summary Statistics
```

### 4.3 模块职责

说明各模块职责：

```text
composer:
将自然语言目标转换为 skill sequence。

skills:
加载、校验和管理 skill 元信息。

harness:
校验、修复、执行和监控 skill sequence，并处理 failed 后的 recover。

backends:
执行具体 skill。第一版使用 DummyBackend。

policies:
预留已经训练好的 skill policy 接口，包括 .pt、.pth、.pkl、.npz 等 checkpoint。

logging_utils:
保存执行日志并生成统计结果。

utils:
提供 YAML、JSON、clamp、打印和异常处理等通用工具。
```

### 4.4 MVP 边界

第一版实现：

```text
Rule-based language-to-skill composition
Skill registry
Skill schema validation
Sequence validation
Transition repair
Dummy backend execution
Recovery after failed execution
ExecutionResult
Execution logs
Summary statistics
Pytest tests
```

第一版预留：

```text
LLM composer
Motion clip backend
Trained skill policy backend
MuJoCo / Gym backend
Isaac Lab backend
TextOp backend
GR00T backend
Real humanoid robot backend
```

### 4.5 与 TextOp 的关系

明确写出：

```text
HumaSkill 是一个 skill-level composition and execution harness。
它位于 motion generation 系统上层，负责 skill sequence composition、transition repair、execution monitoring 和 recovery handling。

TextOp 类系统后续可以作为 backend 接入 HumaSkill。
```

### 4.6 与已经训练好的 skill policy 的关系

明确写出：

```text
HumaSkill 负责高层 skill 组合、衔接修复、执行监控和恢复逻辑。
已经训练好的 skill policy 负责单个 skill 的低层控制。
TrainedPolicyBackend 负责连接 HumaSkill 和已经训练好的 skill policy。
```

包含如下关系图：

```text
HumaSkill
↓
SkillExecutor
↓
TrainedPolicyBackend
↓
PolicyRegistry
↓
BaseSkillPolicy
↓
MuJoCo / Gym Env
```

---

## 5. INTERFACES.md 要求

创建 `INTERFACES.md`。

这是最重要的文件。它必须定义所有后续 coding agent 共同遵守的共享接口。

### 5.1 SkillInfo

定义：

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class SkillInfo:
    name: str
    tags: list[str]
    duration_range: tuple[float, float]
    start_pose: str
    end_pose: str
    risk: str
    description: str = ""
    backend: str = "dummy"
    policy_id: str | None = None
    checkpoint: str | None = None
    action_type: str | None = None
    obs_adapter: str | None = None
```

字段含义：

```text
name:
skill 名称。

tags:
skill 标签。

duration_range:
允许的持续时间范围。

start_pose:
启动姿态要求。

end_pose:
预期结束姿态。

risk:
skill 风险等级。允许值为 low、medium、high。

description:
面向人类阅读的 skill 描述。

backend:
该 skill 使用的 backend。第一版默认为 dummy。

policy_id:
后续训练策略使用的策略 ID。

checkpoint:
后续训练策略使用的 checkpoint 路径。

action_type:
后续仿真策略使用的动作类型，例如 joint_position、torque、velocity_command。

obs_adapter:
后续训练策略使用的 observation adapter 名称。
```

### 5.2 Raw Sequence Item

Composer 输出 item：

```python
{
    "skill": "arm_wave",
    "duration": 1.5
}
```

规则：

```text
skill 必须是字符串。
duration 必须为正数。
raw sequence 由 composer 生成。
raw sequence 进入 TransitionManager 之前由 SequenceValidator 校验。
```

### 5.3 Repaired Sequence Item

TransitionManager 输出 item：

```python
{
    "skill": "stand_stable",
    "duration": 0.8,
    "source": "transition_inserted"
}
```

允许的 `source` 值：

```text
agent
transition_inserted
recovery_inserted
duration_clamped
```

含义：

```text
agent:
该 item 来自 composer 输出。

transition_inserted:
该 item 由 TransitionManager 插入。

recovery_inserted:
该 item 由执行阶段恢复逻辑插入。

duration_clamped:
原始 item 的 duration 超出范围，已被 clamp 到合法范围。
```

每个 repaired sequence item 必须包含：

```text
skill
duration
source
```

### 5.4 ExecutionResult

Backend 执行 skill 后必须返回结构化结果，不能只返回原始字符串。

定义：

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionResult:
    status: str
    skill: str
    duration: float
    steps: int = 0
    reward: float | None = None
    final_obs: dict[str, Any] | None = None
    info: dict[str, Any] = field(default_factory=dict)
    failure_reason: str | None = None
```

允许的 `status` 值：

```text
success
failed
```

字段含义：

```text
status:
skill 执行状态。

skill:
被执行的 skill 名称。

duration:
计划执行时长。

steps:
backend 环境 step 数。

reward:
backend 返回的累计 reward，可以为空。

final_obs:
skill 执行后的最终 observation，可以为空。

info:
backend 额外信息。

failure_reason:
失败原因，可以为空。
```

DummyBackend 可以只填充：

```text
status
skill
duration
steps
failure_reason
info
```

后续 MuJoCo / Gym backend 可以填充：

```text
steps
reward
final_obs
info
terminated
truncated
```

后续 trained skill policy backend 可以在 `info` 中包含：

```text
policy_id
checkpoint
obs_adapter
action_type
env_steps
```

### 5.5 Execution Log Item

执行日志 item：

```python
{
    "index": 0,
    "skill": "stand_ready",
    "duration": 1.0,
    "source": "agent",
    "status": "success",
    "start_time": 0.0,
    "end_time": 1.0,
    "backend_steps": 0,
    "backend_reward": None,
    "failure_reason": None,
    "backend_info": {}
}
```

允许的 `status` 值：

```text
success
failed
```

规则：

```text
start_time 和 end_time 可以使用计划时间累计。
第一版不需要真实 sleep。
日志中的 status 来自 ExecutionResult.status。
backend_info 来自 ExecutionResult.info。
```

### 5.6 Backend Interface

定义：

```python
from abc import ABC, abstractmethod


class BaseBackend(ABC):
    @abstractmethod
    def execute(self, skill_name: str, duration: float) -> ExecutionResult:
        """Execute a skill and return a structured execution result."""
        raise NotImplementedError
```

Backend 必须返回 `ExecutionResult`。

`ExecutionResult.status` 只能是：

```text
success
failed
```

### 5.7 Composer Interface

定义：

```python
from abc import ABC, abstractmethod


class BaseComposer(ABC):
    @abstractmethod
    def compose(self, text: str, duration: float, seed: int | None = None) -> list[dict]:
        """Convert a language instruction into a raw skill sequence."""
        raise NotImplementedError
```

### 5.8 Policy Interface

用于后续接入已经训练好的 skill policy：

```python
from abc import ABC, abstractmethod
from typing import Any


class BaseSkillPolicy(ABC):
    @abstractmethod
    def reset(self, skill_name: str, skill_param: dict | None = None) -> None:
        """Reset internal policy state before executing a skill."""
        raise NotImplementedError

    @abstractmethod
    def act(self, obs: dict[str, Any]) -> Any:
        """Return low-level action from policy observation."""
        raise NotImplementedError
```

### 5.9 PolicyRegistry Interface

用于后续 skill 到 policy 的映射：

```python
register(skill_name: str, policy: BaseSkillPolicy) -> None
get(skill_name: str) -> BaseSkillPolicy
has(skill_name: str) -> bool
all_names() -> list[str]
```

### 5.10 PolicyAdapter Interface

用于后续环境 observation 转换：

```python
class PolicyAdapter:
    def build_policy_obs(self, skill_name: str, env_obs: dict) -> dict:
        """Convert environment observation to policy observation."""
        raise NotImplementedError
```

### 5.11 CheckpointLoader Interface

用于后续加载已经训练好的 policy checkpoint：

```python
class CheckpointLoader:
    def load(self, checkpoint_path: str) -> BaseSkillPolicy:
        """Load a pretrained skill policy from checkpoint."""
        raise NotImplementedError
```

### 5.12 SkillRegistry Interface

必须提供：

```python
get(name: str) -> SkillInfo
has(name: str) -> bool
all_names() -> list[str]
skills_with_tag(tag: str) -> list[SkillInfo]
```

查询未知 skill 时必须抛出 `UnknownSkillError`。

### 5.13 Required Exceptions

定义：

```python
class HumaSkillError(Exception):
    pass


class UnknownSkillError(HumaSkillError):
    pass


class InvalidSkillConfigError(HumaSkillError):
    pass


class InvalidSequenceError(HumaSkillError):
    pass


class BackendExecutionError(HumaSkillError):
    pass


class PolicyLoadError(HumaSkillError):
    pass
```

### 5.14 Transition Repair Rules

TransitionManager 必须遵守：

```text
1. composer 输出 item 标记 source = agent。
2. 当 duration 超出 skill duration_range 时进行 clamp。
3. 如果 duration 被 clamp，标记 source = duration_clamped。
4. 如果 current pose 匹配 next skill start_pose，保留该 item。
5. 如果 start_pose 为 any，允许从任意 pose 启动。
6. 如果 current pose 为 low_pose，且下一个 skill 需要 standing，优先插入 stand_up。
7. 如果 current pose 和 next skill start_pose 不匹配，插入 stand_stable。
8. high risk skill 之前插入 stand_stable。
9. high risk skill 之后插入 stand_stable。
10. medium risk skill 之后插入 stand_stable。
11. 所有插入 item 必须包含 source。
12. 所有输出 item 必须包含 skill、duration、source。
```

默认插入时长：

```text
stand_stable: 0.8
stand_up: 1.2
recover: 1.5
```

### 5.15 Required Commands

最终项目必须支持：

```bash
python scripts/validate_skills.py
python -m humaskill.main --text "跳一段 12 秒的欢快机器人舞蹈" --duration 12 --seed 42 --fail-prob 0.1 --backend dummy --output logs/demo_log.json
pytest -q
```

---

## 6. TASKS.md 要求

创建 `TASKS.md`。

将项目拆分为六个实现任务。

### Task 01: Project Skeleton and Configs

负责文件：

```text
README.md
requirements.txt
pyproject.toml
.gitignore
configs/skills.yaml
configs/default_config.yaml
examples/
logs/.gitkeep
empty package files
```

目标：

```text
创建完整项目结构。
创建配置文件。
创建示例输入和输出文件。
创建空模块文件。
```

### Task 02: Utils and Skill Registry

负责文件：

```text
humaskill/utils/
humaskill/skills/
tests/test_skill_registry.py
scripts/validate_skills.py
```

目标：

```text
实现自定义异常。
实现 YAML 和 JSON 工具。
实现 clamp 工具。
实现 SkillInfo。
实现 skill schema validation。
实现 SkillRegistry。
实现 skill config validation script。
补充 pytest。
```

### Task 03: Composer

负责文件：

```text
humaskill/composer/
tests/test_composer.py
```

目标：

```text
实现 BaseComposer。
实现 RuleBasedDanceComposer。
预留 LLMComposer。
补充 composer tests。
```

### Task 04: Transition and Validation

负责文件：

```text
humaskill/harness/sequence_validator.py
humaskill/harness/transition_manager.py
humaskill/harness/safety_supervisor.py
tests/test_transition_manager.py
```

目标：

```text
实现 sequence validation。
实现 transition repair。
实现 SafetySupervisor。
补充 transition tests。
```

### Task 05: Backend, Policy Interface, and Executor

负责文件：

```text
humaskill/backends/
humaskill/policies/
humaskill/harness/skill_executor.py
tests/test_backend.py
tests/test_executor.py
```

目标：

```text
实现 BaseBackend。
实现 ExecutionResult。
实现 DummyDanceBackend。
预留 MotionClipBackend、TrainedPolicyBackend、MujocoGymBackend、IsaacLabBackend、TextOpBackend、GrootBackend。
实现 BaseSkillPolicy、PolicyRegistry、PolicyAdapter、CheckpointLoader 占位接口。
实现 SkillExecutor。
补充 backend 和 executor tests。
```

### Task 06: Main, Logging, README Finalization, and Integration Fixes

负责文件：

```text
humaskill/main.py
humaskill/logging_utils/
scripts/run_demo.py
README.md
integration fixes
```

目标：

```text
实现 CLI main entry。
实现 execution log saving。
实现 summary statistics。
实现 demo script。
完善 README。
运行 demo。
运行 pytest。
```

---

## 7. AGENT_ASSIGNMENTS.md 要求

创建 `AGENT_ASSIGNMENTS.md`。

推荐分工：

```text
Claude Code:
Task 01, Task 05, Task 06

DeepSeek TUI:
Task 02, Task 03, Task 04

Codex CLI:
本地测试执行、import 清理、小 bug 修复、失败测试修复

Codex App:
最终审查、接口一致性审查、最小定向修复

Hermes:
项目经理、接口守门员、验收检查员、最终编排者
```

解释每个角色：

```text
Claude Code 适合负责项目骨架、复杂集成、backend、policy interface、executor 和 main entry。

DeepSeek TUI 适合负责模块化实现和测试。

Codex CLI 适合负责命令行测试执行、本地 bug 修复、import 清理和小补丁。

Codex App 适合负责最终项目审查、接口一致性检查、隐藏 bug 检测和最小定向修复。

Hermes 维护 INTERFACES.md 一致性，检查 agent 是否只修改允许文件，并运行验收检查。
```

---

## 8. DEVELOPMENT_ORDER.md 要求

创建 `DEVELOPMENT_ORDER.md`。

推荐顺序：

```text
1. 运行 agent_prompts/01_skeleton_prompt.md
2. 运行 agent_prompts/02_skills_registry_prompt.md
3. 运行 agent_prompts/03_composer_prompt.md
4. 运行 agent_prompts/04_transition_prompt.md
5. 运行 agent_prompts/05_backend_executor_prompt.md
6. 运行 agent_prompts/06_main_readme_testfix_prompt.md
7. 使用 Codex CLI 做本地修复和失败测试修复
8. 使用 Codex App 做最终审查
9. 使用 Hermes 做最终验收
```

同时写明：

```text
每个 subagent 开始前必须阅读 PROJECT_PLAN.md、INTERFACES.md、TASKS.md 和 ACCEPTANCE_CHECKLIST.md。
每个 subagent 只能编辑当前 prompt 允许的文件。
```

---

## 9. ACCEPTANCE_CHECKLIST.md 要求

创建 `ACCEPTANCE_CHECKLIST.md`。

必须包含以下命令：

```bash
cd HumaSkill
pip install -r requirements.txt
python scripts/validate_skills.py
python -m humaskill.main --text "跳一段 12 秒的欢快机器人舞蹈" --duration 12 --seed 42 --fail-prob 0.1 --backend dummy --output logs/demo_log.json
pytest -q
```

验收标准：

```text
项目结构符合约定架构。
skills.yaml 可以被 validate_skills.py 加载。
demo 命令可以成功运行。
logs/demo_log.json 可以生成。
pytest 全部通过。
README 解释项目定位以及与 TextOp 的关系。
所有 placeholder backend class 存在。
ExecutionResult 接口存在。
TrainedPolicyBackend placeholder 存在。
MujocoGymBackend placeholder 存在。
policies 目录和基础接口存在。
所有核心接口符合 INTERFACES.md。
Backend.execute 返回 ExecutionResult。
Executor logs 使用 status，而不是原始 result 字符串。
```

---

## 10. TEST_PLAN.md 要求

创建 `TEST_PLAN.md`。

### test_composer.py

必须覆盖：

```text
Composer output 以 stand_ready 开始。
Composer output 以 final_pose 结束。
相同 seed 产生相同输出。
总 duration 接近目标 duration。
不同风格关键词影响选取的 skill pool。
```

### test_skill_registry.py

必须覆盖：

```text
skills.yaml 成功加载。
stand_ready 存在。
recover 存在。
all_names 返回 list。
未知 skill 抛出 UnknownSkillError。
新增字段 backend、policy_id、checkpoint、action_type、obs_adapter 可以被加载。
```

### test_transition_manager.py

必须覆盖：

```text
High risk skill 前后插入 stand_stable。
Medium risk skill 后插入 stand_stable。
squat 后接 standing skill 插入 stand_up。
超出范围的 duration 被 clamp。
未知 skill 抛出错误。
每个 repaired item 包含 skill、duration、source。
```

### test_executor.py

必须覆盖：

```text
Executor 可以执行完整 repaired sequence。
Backend failed 触发 recover。
Logs 包含 skill、duration、source、status、start_time、end_time。
Logs 包含 backend_steps、backend_reward、failure_reason、backend_info。
Summary 字段正确。
```

### test_backend.py

必须覆盖：

```text
DummyDanceBackend 返回 ExecutionResult。
DummyDanceBackend 默认 status 为 success。
turn_left、turn_right、squat 在 fail_prob 设置后可以 failed。
相同 seed 产生可复现结果。
ExecutionResult.status 只使用 success 或 failed。
TrainedPolicyBackend、MujocoGymBackend、MotionClipBackend、IsaacLabBackend、TextOpBackend、GrootBackend 占位类存在。
```

---

## 11. agent_prompts 要求

创建六个实现 prompt 和一个最终审查 prompt。

每个 subagent prompt 必须包含：

```text
Task goal
Allowed files to edit
Interfaces to follow
Implementation requirements
Tests to run
Acceptance criteria
Restriction against editing unrelated modules
```

每个 subagent prompt 必须要求 agent 阅读：

```text
PROJECT_PLAN.md
INTERFACES.md
TASKS.md
ACCEPTANCE_CHECKLIST.md
```

每个 subagent prompt 必须写明：

```text
Follow INTERFACES.md strictly.
Only edit the files explicitly allowed in this task.
Use Python 3.10+.
Use only PyYAML and pytest.
Backend must return ExecutionResult.
Executor logs must use status.
Tests must not assume backend returns raw strings.
```

### 11.1 agent_prompts/01_skeleton_prompt.md

用于项目骨架和配置。

必须要求创建：

```text
README.md
requirements.txt
pyproject.toml
.gitignore
configs/skills.yaml
configs/default_config.yaml
examples/
logs/.gitkeep
all package __init__.py files
all empty module files
policies directory
trained_policy_backend.py
mujoco_gym_backend.py
```

### 11.2 agent_prompts/02_skills_registry_prompt.md

用于 utils 和 skills。

必须要求实现：

```text
humaskill/utils/errors.py
humaskill/utils/io.py
humaskill/utils/math_utils.py
humaskill/utils/printing.py
humaskill/skills/skill_info.py
humaskill/skills/skill_schema.py
humaskill/skills/skill_registry.py
scripts/validate_skills.py
tests/test_skill_registry.py
```

### 11.3 agent_prompts/03_composer_prompt.md

用于 composer。

必须要求实现：

```text
humaskill/composer/base_composer.py
humaskill/composer/rule_based_composer.py
humaskill/composer/llm_composer.py
tests/test_composer.py
```

### 11.4 agent_prompts/04_transition_prompt.md

用于 transition 和 validation。

必须要求实现：

```text
humaskill/harness/sequence_validator.py
humaskill/harness/transition_manager.py
humaskill/harness/safety_supervisor.py
tests/test_transition_manager.py
```

### 11.5 agent_prompts/05_backend_executor_prompt.md

用于 backend、policy interface 和 executor。

必须要求实现：

```text
humaskill/backends/base_backend.py
humaskill/backends/dummy_backend.py
humaskill/backends/motion_clip_backend.py
humaskill/backends/trained_policy_backend.py
humaskill/backends/mujoco_gym_backend.py
humaskill/backends/isaaclab_backend.py
humaskill/backends/textop_backend.py
humaskill/backends/groot_backend.py
humaskill/policies/base_policy.py
humaskill/policies/policy_registry.py
humaskill/policies/policy_adapter.py
humaskill/policies/checkpoint_loader.py
humaskill/harness/skill_executor.py
tests/test_backend.py
tests/test_executor.py
```

### 11.6 agent_prompts/06_main_readme_testfix_prompt.md

用于 main、logging、README 和 integration fixes。

必须要求实现：

```text
humaskill/main.py
humaskill/logging_utils/execution_logger.py
humaskill/logging_utils/summary.py
scripts/run_demo.py
README.md
integration fixes
```

### 11.7 agent_prompts/07_codex_app_final_review_prompt.md

创建一个专门给 Codex App 使用的最终审查 prompt。

它必须要求 Codex App 阅读：

```text
PROJECT_PLAN.md
INTERFACES.md
TASKS.md
ACCEPTANCE_CHECKLIST.md
TEST_PLAN.md
README.md
```

它必须要求 Codex App 根据 INTERFACES.md 审查完整实现。

它必须检查：

```text
Backend.execute 返回 ExecutionResult。
ExecutionResult.status 被一致使用。
代码没有混用旧的 result 字符串和 status。
每个 repaired sequence item 包含 skill、duration、source。
允许的 source 值为 agent、transition_inserted、recovery_inserted、duration_clamped。
每个 execution log item 包含 index、skill、duration、source、status、start_time、end_time、backend_steps、backend_reward、failure_reason、backend_info。
ExecutionResult.status 只使用 success 或 failed。
SkillInfo 包含 backend、policy_id、checkpoint、action_type、obs_adapter。
MotionClipBackend、TrainedPolicyBackend、MujocoGymBackend、IsaacLabBackend、TextOpBackend、GrootBackend 占位 backend 存在。
BaseSkillPolicy、PolicyRegistry、PolicyAdapter、CheckpointLoader policy 扩展接口存在。
README 清楚解释 HumaSkill、TextOp、trained skill policies 和 MuJoCo / Gym backend。
测试覆盖 composer、skill registry、transition manager、backend 和 executor。
```

它必须要求 Codex App 运行或请求运行：

```bash
python scripts/validate_skills.py
python -m humaskill.main --text "跳一段 12 秒的欢快机器人舞蹈" --duration 12 --seed 42 --fail-prob 0.1 --backend dummy --output logs/demo_log.json
pytest -q
```

它必须按照以下结构报告发现：

```text
Critical issues:
- ...

Interface inconsistencies:
- ...

Test gaps:
- ...

Maintainability issues:
- ...

Documentation issues:
- ...

Future backend integration risks:
- ...

Recommended minimal patch plan:
1. ...
2. ...
3. ...
```

它必须要求 Codex App 优先使用最小定向补丁。

---

## 12. Subagent Prompt 通用约束

每个 subagent prompt 必须要求：

```text
Read PROJECT_PLAN.md, INTERFACES.md, TASKS.md, and ACCEPTANCE_CHECKLIST.md first.
Follow INTERFACES.md strictly.
Only edit files allowed by the current task.
Use Python 3.10+.
Use only PyYAML and pytest.
Write docstrings for core functions.
Use clear exception messages.
Handle paths in a way that works on Windows and Linux.
Backend returns ExecutionResult.
Executor logs use status.
Tests must not assume backend returns raw strings.
```

---

## 13. Hermes 阶段一最终输出要求

阶段一完成后，请总结：

```text
1. 已生成的规划文件
2. INTERFACES.md 中的关键接口
3. ExecutionResult 设计
4. Trained skill policy backend 预留方式
5. MuJoCo / Gym backend 预留方式
6. 六个实现任务
7. 推荐开发顺序
8. 推荐 agent 分工
9. Codex App 最终审查 prompt 路径
10. 下一步应该先运行哪个 prompt
```

现在请创建 `HumaSkill/` 目录，并完成全部阶段一文件。