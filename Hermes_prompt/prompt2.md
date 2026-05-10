# HumaSkill Phase 1: Project Planning, Interface Specification, Task Decomposition, and Agent Prompts

You are the orchestration, planning, and review agent for the HumaSkill project.

Your current task is Phase 1 only.

Phase 1 goal:
Create project management documents, interface specification documents, task decomposition documents, development order documents, acceptance checklists, test plans, and subagent prompts for later coding agents.

In this phase, focus on planning, interface locking, task splitting, and prompt generation. Full implementation will be completed later by coding agents following the generated task prompts.

You may create planning files and task prompt files. You may define final architecture and file structure. Core business logic should be left to later implementation tasks.

---

## 1. Project Name and Positioning

Project name:

```text
HumaSkill
```

Python package name:

```text
humaskill
```

Project positioning:

```text
HumaSkill is a skill-level composition and execution harness for language-guided humanoid motion composition.
```

Chinese positioning:

```text
HumaSkill 是一个面向语言引导人形机器人动作组合的技能级执行框架。
```

The first MVP scenario is:

```text
User input: “跳一段 12 秒的欢快机器人舞蹈”
```

The first MVP system flow is:

```text
Language instruction
↓
Skill sequence generation
↓
Sequence validation
↓
Transition repair
↓
Dummy backend execution
↓
Recovery after failed execution
↓
Execution logs
↓
Summary statistics
```

The first version only implements DummyBackend.

Future extensions should be reserved for:

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

The near-term target is simulation, especially MuJoCo or Gym-style environments. The project should reserve interfaces for pretrained skill policies such as `.pt`, `.pth`, `.pkl`, and `.npz` files. Real humanoid robot execution is a long-term extension.

---

## 2. Phase 1 Required Output Files

Create the following files and directories:

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

These files will be used as the shared contract for all later coding agents.

---

## 3. Final Project Structure

All planning documents and subagent prompts must assume this final project structure:

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

## 4. PROJECT_PLAN.md Requirements

Create `PROJECT_PLAN.md`.

It must include the following sections.

### 4.1 Project Goal

Explain that the first version of HumaSkill aims to:

```text
Convert a natural language goal into a humanoid skill sequence, then improve executability through transition repair, execution monitoring, and recovery handling.
```

### 4.2 System Flow

Include this flow:

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

### 4.3 Module Responsibilities

Explain the responsibilities of each module:

```text
composer:
Converts natural language goals into skill sequences.

skills:
Loads, validates, and manages skill metadata.

harness:
Validates, repairs, executes, and monitors skill sequences. It also handles recovery after failed execution.

backends:
Executes concrete skills. The first version uses DummyBackend.

policies:
Reserves interfaces for pretrained skill policies, including .pt, .pth, .pkl, and .npz checkpoints.

logging_utils:
Saves execution logs and produces summary statistics.

utils:
Provides YAML, JSON, clamp, printing, and exception utilities.
```

### 4.4 MVP Boundary

The first version implements:

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

The first version reserves:

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

### 4.5 Relationship with TextOp

State clearly:

```text
HumaSkill is a skill-level composition and execution harness.
It sits above motion generation systems and is responsible for skill sequence composition, transition repair, execution monitoring, and recovery handling.

TextOp-like systems can be integrated later as backends.
```

### 4.6 Relationship with Pretrained Skill Policies

State clearly:

```text
HumaSkill handles high-level skill composition, transition repair, execution monitoring, and recovery logic.
Pretrained skill policies handle low-level control for individual skills.
TrainedPolicyBackend connects HumaSkill to pretrained skill policies.
```

Include this relationship diagram:

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

## 5. INTERFACES.md Requirements

Create `INTERFACES.md`.

This is the most important file. It must define all shared interfaces that later coding agents must follow.

### 5.1 SkillInfo

Define:

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

Field meanings:

```text
name:
Skill name.

tags:
Skill tags.

duration_range:
Allowed duration range.

start_pose:
Required starting pose.

end_pose:
Expected ending pose.

risk:
Skill risk level. Allowed values: low, medium, high.

description:
Human-readable skill description.

backend:
Backend used by this skill. The first version defaults to dummy.

policy_id:
Policy ID used later by trained skill policies.

checkpoint:
Checkpoint path used later by trained skill policies.

action_type:
Action type used later by simulation policies, such as joint_position, torque, or velocity_command.

obs_adapter:
Observation adapter name used later by trained skill policies.
```

### 5.2 Raw Sequence Item

Composer output item:

```python
{
    "skill": "arm_wave",
    "duration": 1.5
}
```

Rules:

```text
skill must be a string.
duration must be positive.
raw sequence is generated by composer.
raw sequence is validated by SequenceValidator before entering TransitionManager.
```

### 5.3 Repaired Sequence Item

TransitionManager output item:

```python
{
    "skill": "stand_stable",
    "duration": 0.8,
    "source": "transition_inserted"
}
```

Allowed `source` values:

```text
agent
transition_inserted
recovery_inserted
duration_clamped
```

Meanings:

```text
agent:
The item comes from the composer output.

transition_inserted:
The item is inserted by TransitionManager.

recovery_inserted:
The item is inserted by execution-time recovery logic.

duration_clamped:
The original item had an out-of-range duration and was clamped to the valid range.
```

Every repaired sequence item must contain:

```text
skill
duration
source
```

### 5.4 ExecutionResult

Backend execution must return a structured result instead of a raw string.

Define:

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

Allowed `status` values:

```text
success
failed
```

Field meanings:

```text
status:
Skill execution status.

skill:
Executed skill name.

duration:
Planned execution duration.

steps:
Number of backend environment steps.

reward:
Accumulated reward returned by backend. It can be None.

final_obs:
Final observation after skill execution. It can be None.

info:
Extra backend information.

failure_reason:
Failure reason. It can be None.
```

DummyBackend may fill only:

```text
status
skill
duration
steps
failure_reason
info
```

Future MuJoCo / Gym backend may fill:

```text
steps
reward
final_obs
info
terminated
truncated
```

Future trained skill policy backend may include these fields in `info`:

```text
policy_id
checkpoint
obs_adapter
action_type
env_steps
```

### 5.5 Execution Log Item

Execution log item:

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

Allowed `status` values:

```text
success
failed
```

Rules:

```text
start_time and end_time can use planned-time accumulation.
The first version does not need real sleep.
Log status comes from ExecutionResult.status.
backend_info comes from ExecutionResult.info.
```

### 5.6 Backend Interface

Define:

```python
from abc import ABC, abstractmethod


class BaseBackend(ABC):
    @abstractmethod
    def execute(self, skill_name: str, duration: float) -> ExecutionResult:
        """Execute a skill and return a structured execution result."""
        raise NotImplementedError
```

Backend must return `ExecutionResult`.

`ExecutionResult.status` must only be:

```text
success
failed
```

### 5.7 Composer Interface

Define:

```python
from abc import ABC, abstractmethod


class BaseComposer(ABC):
    @abstractmethod
    def compose(self, text: str, duration: float, seed: int | None = None) -> list[dict]:
        """Convert a language instruction into a raw skill sequence."""
        raise NotImplementedError
```

### 5.8 Policy Interface

For future pretrained skill policy integration:

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

For future skill-to-policy mapping:

```python
register(skill_name: str, policy: BaseSkillPolicy) -> None
get(skill_name: str) -> BaseSkillPolicy
has(skill_name: str) -> bool
all_names() -> list[str]
```

### 5.10 PolicyAdapter Interface

For future environment observation conversion:

```python
class PolicyAdapter:
    def build_policy_obs(self, skill_name: str, env_obs: dict) -> dict:
        """Convert environment observation to policy observation."""
        raise NotImplementedError
```

### 5.11 CheckpointLoader Interface

For future pretrained policy checkpoint loading:

```python
class CheckpointLoader:
    def load(self, checkpoint_path: str) -> BaseSkillPolicy:
        """Load a pretrained skill policy from checkpoint."""
        raise NotImplementedError
```

### 5.12 SkillRegistry Interface

Must provide:

```python
get(name: str) -> SkillInfo
has(name: str) -> bool
all_names() -> list[str]
skills_with_tag(tag: str) -> list[SkillInfo]
```

Unknown skill lookup must raise `UnknownSkillError`.

### 5.13 Required Exceptions

Define:

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

TransitionManager must follow:

```text
1. Mark composer output items with source = agent.
2. Clamp duration when it is outside the skill duration_range.
3. If duration is clamped, mark source = duration_clamped.
4. If current pose matches next skill start_pose, keep the item.
5. If start_pose is any, allow execution from any pose.
6. If current pose is low_pose and the next skill requires standing, insert stand_up first.
7. If current pose does not match next skill start_pose, insert stand_stable.
8. Insert stand_stable before high risk skills.
9. Insert stand_stable after high risk skills.
10. Insert stand_stable after medium risk skills.
11. Every inserted item must include source.
12. Every output item must contain skill, duration, source.
```

Default inserted durations:

```text
stand_stable: 0.8
stand_up: 1.2
recover: 1.5
```

### 5.15 Required Commands

Final project must support:

```bash
python scripts/validate_skills.py
python -m humaskill.main --text "跳一段 12 秒的欢快机器人舞蹈" --duration 12 --seed 42 --fail-prob 0.1 --backend dummy --output logs/demo_log.json
pytest -q
```

---

## 6. TASKS.md Requirements

Create `TASKS.md`.

Split the project into six implementation tasks.

### Task 01: Project Skeleton and Configs

Responsible files:

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

Goal:

```text
Create complete project structure.
Create configuration files.
Create example input and output files.
Create empty module files.
```

### Task 02: Utils and Skill Registry

Responsible files:

```text
humaskill/utils/
humaskill/skills/
tests/test_skill_registry.py
scripts/validate_skills.py
```

Goal:

```text
Implement custom exceptions.
Implement YAML and JSON utilities.
Implement clamp utility.
Implement SkillInfo.
Implement skill schema validation.
Implement SkillRegistry.
Implement skill config validation script.
Add pytest coverage.
```

### Task 03: Composer

Responsible files:

```text
humaskill/composer/
tests/test_composer.py
```

Goal:

```text
Implement BaseComposer.
Implement RuleBasedDanceComposer.
Reserve LLMComposer.
Add composer tests.
```

### Task 04: Transition and Validation

Responsible files:

```text
humaskill/harness/sequence_validator.py
humaskill/harness/transition_manager.py
humaskill/harness/safety_supervisor.py
tests/test_transition_manager.py
```

Goal:

```text
Implement sequence validation.
Implement transition repair.
Implement SafetySupervisor.
Add transition tests.
```

### Task 05: Backend, Policy Interface, and Executor

Responsible files:

```text
humaskill/backends/
humaskill/policies/
humaskill/harness/skill_executor.py
tests/test_backend.py
tests/test_executor.py
```

Goal:

```text
Implement BaseBackend.
Implement ExecutionResult.
Implement DummyDanceBackend.
Reserve MotionClipBackend, TrainedPolicyBackend, MujocoGymBackend, IsaacLabBackend, TextOpBackend, and GrootBackend.
Implement BaseSkillPolicy, PolicyRegistry, PolicyAdapter, and CheckpointLoader placeholder interfaces.
Implement SkillExecutor.
Add backend and executor tests.
```

### Task 06: Main, Logging, README Finalization, and Integration Fixes

Responsible files:

```text
humaskill/main.py
humaskill/logging_utils/
scripts/run_demo.py
README.md
integration fixes
```

Goal:

```text
Implement CLI main entry.
Implement execution log saving.
Implement summary statistics.
Implement demo script.
Finalize README.
Run demo.
Run pytest.
```

---

## 7. AGENT_ASSIGNMENTS.md Requirements

Create `AGENT_ASSIGNMENTS.md`.

Recommended assignment:

```text
Claude Code:
Task 01, Task 05, Task 06

DeepSeek TUI:
Task 02, Task 03, Task 04

Codex CLI:
Local test execution, import cleanup, small bug fixes, failed test repair

Codex App:
Final review, interface consistency review, minimal targeted patches

Hermes:
Project manager, interface guardian, acceptance checker, final orchestration
```

Explain each role:

```text
Claude Code is suitable for project skeleton, complex integration, backend, policy interface, executor, and main entry.

DeepSeek TUI is suitable for modular implementation and tests.

Codex CLI is suitable for command-line test execution, local bug fixing, import cleanup, and small patches.

Codex App is suitable for final project review, interface consistency review, hidden bug detection, and minimal targeted fixes.

Hermes maintains INTERFACES.md consistency, checks whether agents modify only allowed files, and runs acceptance checks.
```

---

## 8. DEVELOPMENT_ORDER.md Requirements

Create `DEVELOPMENT_ORDER.md`.

Recommended order:

```text
1. Run agent_prompts/01_skeleton_prompt.md
2. Run agent_prompts/02_skills_registry_prompt.md
3. Run agent_prompts/03_composer_prompt.md
4. Run agent_prompts/04_transition_prompt.md
5. Run agent_prompts/05_backend_executor_prompt.md
6. Run agent_prompts/06_main_readme_testfix_prompt.md
7. Use Codex CLI for local fixes and failed tests
8. Use Codex App for final review
9. Use Hermes for final acceptance
```

Also state:

```text
Each subagent must read PROJECT_PLAN.md, INTERFACES.md, TASKS.md, and ACCEPTANCE_CHECKLIST.md before starting.
Each subagent may only edit files allowed by its prompt.
```

---

## 9. ACCEPTANCE_CHECKLIST.md Requirements

Create `ACCEPTANCE_CHECKLIST.md`.

Must include these commands:

```bash
cd HumaSkill
pip install -r requirements.txt
python scripts/validate_skills.py
python -m humaskill.main --text "跳一段 12 秒的欢快机器人舞蹈" --duration 12 --seed 42 --fail-prob 0.1 --backend dummy --output logs/demo_log.json
pytest -q
```

Acceptance criteria:

```text
Project structure matches the agreed architecture.
skills.yaml can be loaded by validate_skills.py.
Demo command runs successfully.
logs/demo_log.json is generated.
pytest passes.
README explains project positioning and relationship with TextOp.
All placeholder backend classes exist.
ExecutionResult interface exists.
TrainedPolicyBackend placeholder exists.
MujocoGymBackend placeholder exists.
policies directory and base interfaces exist.
All core interfaces match INTERFACES.md.
Backend.execute returns ExecutionResult.
Executor logs use status rather than raw result strings.
```

---

## 10. TEST_PLAN.md Requirements

Create `TEST_PLAN.md`.

### test_composer.py

Must cover:

```text
Composer output starts with stand_ready.
Composer output ends with final_pose.
Same seed produces same output.
Total duration is close to target duration.
Different style keywords affect selected skill pool.
```

### test_skill_registry.py

Must cover:

```text
skills.yaml loads successfully.
stand_ready exists.
recover exists.
all_names returns list.
Unknown skill raises UnknownSkillError.
New fields backend, policy_id, checkpoint, action_type, and obs_adapter are loaded.
```

### test_transition_manager.py

Must cover:

```text
High risk skill inserts stand_stable before and after.
Medium risk skill inserts stand_stable after.
squat followed by standing skill inserts stand_up.
Out-of-range duration is clamped.
Unknown skill raises error.
Every repaired item contains skill, duration, source.
```

### test_executor.py

Must cover:

```text
Executor executes a complete repaired sequence.
Failed backend result triggers recover.
Logs contain skill, duration, source, status, start_time, end_time.
Logs contain backend_steps, backend_reward, failure_reason, backend_info.
Summary fields are correct.
```

### test_backend.py

Must cover:

```text
DummyDanceBackend returns ExecutionResult.
DummyDanceBackend default status is success.
turn_left, turn_right, and squat can fail when fail_prob is set.
Same seed produces reproducible results.
ExecutionResult.status only uses success or failed.
Placeholder classes exist for TrainedPolicyBackend, MujocoGymBackend, MotionClipBackend, IsaacLabBackend, TextOpBackend, and GrootBackend.
```

---

## 11. agent_prompts Requirements

Create six implementation prompts and one final review prompt.

Each subagent prompt must include:

```text
Task goal
Allowed files to edit
Interfaces to follow
Implementation requirements
Tests to run
Acceptance criteria
Restriction against editing unrelated modules
```

Every subagent prompt must require the agent to read:

```text
PROJECT_PLAN.md
INTERFACES.md
TASKS.md
ACCEPTANCE_CHECKLIST.md
```

Every subagent prompt must state:

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

For project skeleton and configs.

Must require creating:

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

For utils and skills.

Must require implementing:

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

For composer.

Must require implementing:

```text
humaskill/composer/base_composer.py
humaskill/composer/rule_based_composer.py
humaskill/composer/llm_composer.py
tests/test_composer.py
```

### 11.4 agent_prompts/04_transition_prompt.md

For transition and validation.

Must require implementing:

```text
humaskill/harness/sequence_validator.py
humaskill/harness/transition_manager.py
humaskill/harness/safety_supervisor.py
tests/test_transition_manager.py
```

### 11.5 agent_prompts/05_backend_executor_prompt.md

For backend, policy interface, and executor.

Must require implementing:

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

For main, logging, README, and integration fixes.

Must require implementing:

```text
humaskill/main.py
humaskill/logging_utils/execution_logger.py
humaskill/logging_utils/summary.py
scripts/run_demo.py
README.md
integration fixes
```

### 11.7 agent_prompts/07_codex_app_final_review_prompt.md

Create a dedicated final review prompt for Codex App.

It must instruct Codex App to read:

```text
PROJECT_PLAN.md
INTERFACES.md
TASKS.md
ACCEPTANCE_CHECKLIST.md
TEST_PLAN.md
README.md
```

It must instruct Codex App to review the full implementation against INTERFACES.md.

It must check:

```text
Backend.execute returns ExecutionResult.
ExecutionResult.status is used consistently.
The code does not mix old result strings with status.
Every repaired sequence item contains skill, duration, source.
Allowed source values are agent, transition_inserted, recovery_inserted, duration_clamped.
Every execution log item contains index, skill, duration, source, status, start_time, end_time, backend_steps, backend_reward, failure_reason, backend_info.
ExecutionResult.status only uses success or failed.
SkillInfo includes backend, policy_id, checkpoint, action_type, obs_adapter.
Placeholder backends exist for MotionClipBackend, TrainedPolicyBackend, MujocoGymBackend, IsaacLabBackend, TextOpBackend, and GrootBackend.
Policy extension interfaces exist for BaseSkillPolicy, PolicyRegistry, PolicyAdapter, and CheckpointLoader.
README explains HumaSkill, TextOp, trained skill policies, and MuJoCo / Gym backend clearly.
Tests cover composer, skill registry, transition manager, backend, and executor.
```

It must ask Codex App to run or request running:

```bash
python scripts/validate_skills.py
python -m humaskill.main --text "跳一段 12 秒的欢快机器人舞蹈" --duration 12 --seed 42 --fail-prob 0.1 --backend dummy --output logs/demo_log.json
pytest -q
```

It must report findings in this structure:

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

It must instruct Codex App to prefer minimal targeted patches.

---

## 12. Subagent Prompt Common Constraints

Each subagent prompt must require:

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

## 13. Final Output Required from Hermes

After completing Phase 1, summarize:

```text
1. Generated planning files
2. Key interfaces in INTERFACES.md
3. ExecutionResult design
4. Trained skill policy backend reservation
5. MuJoCo / Gym backend reservation
6. Six implementation tasks
7. Recommended development order
8. Recommended agent assignment
9. Codex App final review prompt location
10. The next prompt to run first
```

Now create the `HumaSkill/` directory and complete all Phase 1 files.