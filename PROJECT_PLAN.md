# HumaSkill — Project Plan

## Project Goal

HumaSkill is a skill-level composition and execution harness for language-guided humanoid motion composition.

The first version (MVP) converts natural language goals into humanoid skill sequences, and improves sequence executability through transition repair, execution monitoring, and recovery handling.

### MVP Use Case

```
User input: "跳一段 12 秒的欢快机器人舞蹈"
```

### MVP System Flow

```
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

### MVP Scope

First version implements:

- Rule-based language-to-skill composition
- Skill registry (from YAML config)
- Skill schema validation
- Sequence validation
- Transition repair (pose matching, risk-based insertion, duration clamping)
- Dummy backend execution
- Recovery after failed execution (`failed` → `recover`)
- Structured `ExecutionResult`
- Execution logs (time, status, backend info)
- Summary statistics
- Pytest tests

First version reserves (placeholder classes only):

- LLM composer
- Motion clip backend
- Trained skill policy backend
- MuJoCo / Gym backend
- Isaac Lab backend
- TextOp backend
- GR00T backend
- Real humanoid robot backend

---

## Module Responsibilities

### composer
Converts natural language instruction into a raw skill sequence.

### skills
Loads, validates, and manages skill metadata (`SkillInfo`). Provides `SkillRegistry` for lookups by name and tag.

### harness
Validates, repairs, executes, and monitors skill sequences. Handles recovery on failed execution.

- **SequenceValidator**: validates raw sequence items
- **TransitionManager**: repairs transitions (pose matching, risk inserts, duration clamping)
- **SkillExecutor**: executes repaired sequence through a backend, handles recover on fail
- **SafetySupervisor**: monitors safety during execution

### backends
Executes individual skills. MVP uses `DummyDanceBackend`. Returns `ExecutionResult`.

### policies
Reserved interface for pre-trained skill policies (`.pt`, `.pth`, `.pkl`, `.npz` checkpoints).

### logging_utils
Saves execution logs and generates summary statistics.

### utils
Provides YAML/JSON I/O, math utilities (clamp), printing helpers, and custom exceptions.

---

## MVP Boundary

| Implemented (MVP) | Reserved (placeholder only) |
|---|---|
| RuleBasedDanceComposer | LLMComposer |
| SkillInfo + SkillRegistry | — |
| Skill schema validation | — |
| SequenceValidator | — |
| TransitionManager | — |
| DummyDanceBackend | MotionClipBackend, TrainedPolicyBackend, MujocoGymBackend, IsaacLabBackend, TextOpBackend, GrootBackend |
| SkillExecutor with recovery | — |
| ExecutionResult | — |
| Execution logs + summary | — |
| Pytest tests | — |

---

## Relationship with TextOp

HumaSkill is a **skill-level composition and execution harness**. It sits above motion generation systems and is responsible for skill sequence composition, transition repair, execution monitoring, and recovery handling.

TextOp-class systems can later be integrated as a **backend** into HumaSkill.

---

## Relationship with Trained Skill Policies

HumaSkill handles high-level skill composition, transition repair, execution monitoring, and recovery logic.

Pre-trained skill policies handle low-level control for individual skills.

`TrainedPolicyBackend` connects HumaSkill to pre-trained skill policies.

```
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

## Project Structure

```
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

## Key Design Decisions

1. **Backend returns `ExecutionResult`, not raw strings** — ensures typed, structured communication between executor and backend.
2. **`source` field on all sequence items** — tracks provenance (`agent`, `transition_inserted`, `recovery_inserted`, `duration_clamped`).
3. **`status` field uses only `success` / `failed`** — binary result with optional `failure_reason` for details.
4. **All placeholder backends exist as classes** — ensures future backends have clear integration points.
5. **`policies/` directory exists from day one** — pre-trained skill policy integration is designed in, not bolted on.
