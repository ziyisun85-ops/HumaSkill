# HumaSkill

Skill-level composition and execution harness for language-guided humanoid motion composition.

HumaSkill sits **above** low-level motion generation and handles the *what* and *when*:
- Natural language → skill sequence composition
- Sequence validation
- Transition repair (pose matching, risk-based safety inserts, duration clamping)
- Execution monitoring with automatic recovery on failure
- Structured logging and summary statistics

It does **NOT** generate motion trajectories itself — that is the backends' job.

---

## Project Positioning

HumaSkill is a **skill-level composition harness**. It composes high-level skill sequences from natural language instructions, validates them against a skill registry, repairs unsafe transitions, executes through a pluggable backend, and handles recovery when execution fails.

Think of it as the "conductor" that decides *which* skills to perform, *in what order*, and *how to recover* if something goes wrong — while the backends (dummy / motion clip / trained policy / MuJoCo Gym / Isaac Lab / TextOp / GR00T) handle the low-level *how to move*.

---

## Relationship with TextOp

HumaSkill handles skill-level composition, transition repair, execution monitoring, and recovery.

TextOp and similar text-to-motion generation systems operate at a different level — they generate motion trajectories from text. These systems can later be integrated as **backends** into HumaSkill.

The `TextOpBackend` placeholder class already exists in `humaskill/backends/textop_backend.py`, reserving the integration point for future use.

```
HumaSkill (skill composition & execution harness)
    ↓
SkillExecutor
    ↓
TextOpBackend (placeholder)  ← future integration point
    ↓
Text-to-motion generation system
```

---

## Relationship with Trained Skill Policies

HumaSkill handles high-level skill composition, transition repair, execution monitoring, and recovery.

Pre-trained skill policies handle low-level control for individual skills.

`TrainedPolicyBackend` (placeholder) connects HumaSkill to pre-trained skill policies loaded from checkpoints (`.pt`, `.pth`, `.pkl`, `.npz`).

The `policies/` directory exists from day one:

```
policies/
  base_policy.py       — BaseSkillPolicy ABC
  policy_registry.py   — PolicyRegistry for lookup
  policy_adapter.py    — PolicyAdapter (obs conversion)
  checkpoint_loader.py — CheckpointLoader (.pt/.pth/.pkl/.npz)
```

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

## MuJoCo / Gym Backend

The `MujocoGymBackend` placeholder reserves the integration point for MuJoCo or Gymnasium-based physics simulation environments.

Future: execute HumaSkill skill sequences in physics simulation, producing trajectories with joint positions, torques, or velocity commands. The `ExecutionResult` dataclass already includes fields for `steps`, `reward`, and `final_obs` that future MuJoCo/Gym backends will populate.

---

## Project Structure

```
HumaSkill/
  README.md
  requirements.txt
  pyproject.toml
  .gitignore

  configs/
    skills.yaml              # Skill definitions (12 skills)
    default_config.yaml

  humaskill/
    __init__.py
    main.py                  # CLI entry point

    composer/                # Language → skill sequence
      base_composer.py       #   BaseComposer ABC
      rule_based_composer.py #   RuleBasedDanceComposer (MVP)
      llm_composer.py        #   LLMComposer (placeholder)

    skills/                  # Skill metadata & registry
      skill_info.py          #   SkillInfo dataclass
      skill_registry.py      #   SkillRegistry
      skill_schema.py        #   Schema validation

    harness/                 # Validation, repair, execution
      sequence_validator.py  #   SequenceValidator
      transition_manager.py  #   TransitionManager (12 rules)
      skill_executor.py      #   SkillExecutor with recovery
      safety_supervisor.py   #   SafetySupervisor

    backends/                # Skill execution backends
      base_backend.py        #   BaseBackend ABC + ExecutionResult
      dummy_backend.py       #   DummyDanceBackend (MVP)
      motion_clip_backend.py #   MotionClipBackend (placeholder)
      trained_policy_backend.py  # TrainedPolicyBackend (placeholder)
      mujoco_gym_backend.py  #   MujocoGymBackend (placeholder)
      isaaclab_backend.py    #   IsaacLabBackend (placeholder)
      textop_backend.py      #   TextOpBackend (placeholder)
      groot_backend.py       #   GrootBackend (placeholder)

    policies/                # Pre-trained skill policies (future)
      base_policy.py
      policy_registry.py
      policy_adapter.py
      checkpoint_loader.py

    logging_utils/           # Logging & summary
      execution_logger.py    #   JSON log saving
      summary.py             #   Summary statistics

    utils/                   # Shared utilities
      errors.py              #   Custom exceptions
      io.py                  #   YAML/JSON I/O
      math_utils.py          #   clamp utility
      printing.py            #   Formatted printing

  scripts/
    run_demo.py              # Demo script
    validate_skills.py       # Skill config validator

  examples/
    demo_dance_request.json
    demo_raw_sequence.json
    demo_repaired_sequence.json

  logs/
    .gitkeep

  tests/
    test_composer.py
    test_skill_registry.py
    test_transition_manager.py
    test_executor.py
    test_backend.py
```

---

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd HumaSkill

# Install dependencies (Python 3.10+)
pip install -r requirements.txt

# Verify skill configuration
python scripts/validate_skills.py
```

**Dependencies:** Python 3.10+, PyYAML, pytest.

---

## Usage

### Command-Line Interface

```bash
# Run with demo parameters
python -m humaskill.main \
  --text "跳一段 12 秒的欢快机器人舞蹈" \
  --duration 12 \
  --seed 42 \
  --fail-prob 0.1 \
  --backend dummy \
  --output logs/demo_log.json

# Or use the convenience demo script
python scripts/run_demo.py
```

### CLI Reference

```
usage: python -m humaskill.main [-h] --text TEXT --duration DURATION
                                [--seed SEED] [--fail-prob FAIL_PROB]
                                [--backend BACKEND] [--output OUTPUT]

arguments:
  --text TEXT             Natural language instruction (Chinese)
  --duration DURATION     Target total duration in seconds
  --seed SEED             Random seed for reproducibility (default: 42)
  --fail-prob FAIL_PROB   Failure probability 0.0–1.0 (default: 0.1)
  --backend BACKEND       Execution backend name (default: 'dummy')
  --output OUTPUT         Path to save execution logs as JSON (optional)
```

### Programmatic Usage

```python
from humaskill.main import main

# Run with custom arguments
exit_code = main([
    "--text", "跳一段 12 秒的欢快机器人舞蹈",
    "--duration", "12",
    "--seed", "42",
    "--fail-prob", "0.1",
    "--backend", "dummy",
    "--output", "logs/demo_log.json",
])
```

---

## Supported Backends

| Backend | Status | Description |
|---|---|---|
| `dummy` | **Implemented (MVP)** | Rule-based dummy execution with configurable failure probability |
| `motion_clip` | Placeholder | Pre-recorded motion clip playback |
| `trained_policy` | Placeholder | Pre-trained skill policy inference |
| `mujoco_gym` | Placeholder | MuJoCo / Gymnasium physics simulation |
| `isaaclab` | Placeholder | NVIDIA Isaac Lab simulation |
| `textop` | Placeholder | Text-to-motion generation |
| `groot` | Placeholder | GR00T foundation model |

---

## System Flow

```
User Text (Chinese)
    ↓
Composer Agent        →  RuleBasedDanceComposer maps keywords to skill tags
    ↓
Raw Skill Sequence    →  [{"skill": "arm_wave", "duration": 1.5}, ...]
    ↓
Sequence Validator    →  Validates skills exist, durations positive
    ↓
Transition Manager    →  12 repair rules: pose matching, risk inserts, duration clamping
    ↓
Repaired Sequence     →  [{"skill": "stand_stable", "duration": 0.8, "source": "transition_inserted"}, ...]
    ↓
Skill Executor        →  Executes through backend, recovers on failure
    ↓
Backend (dummy)       →  Returns ExecutionResult with status, steps, info
    ↓
Execution Logs        →  11-field structured log entries
    ↓
Summary Statistics    →  Success/fail counts, skill breakdown, recovery info
```

---

## Transition Repair Rules

The `TransitionManager` applies 12 rules in order (from INTERFACES.md §11):

1. Composer output items are marked `source = "agent"`
2. Out-of-range duration → clamp to valid range
3. Clamped duration → mark `source = "duration_clamped"`
4. Matching poses → keep as-is
5. `start_pose = "any"` → allow starting from any pose
6. `low_pose` → `standing`: insert `stand_up`
7. General pose mismatch → insert `stand_stable`
8. Before `high` risk skill → insert `stand_stable`
9. After `high` risk skill → insert `stand_stable`
10. After `medium` risk skill → insert `stand_stable`
11. All inserted items include a `source` field
12. All output items include `skill`, `duration`, `source`

---

## Registered Skills (MVP)

| Skill | Tags | Risk | Pose |
|---|---|---|---|
| `stand_ready` | basic | low | any → standing |
| `stand_stable` | basic | low | any → standing |
| `stand_up` | basic | medium | low_pose → standing |
| `final_pose` | basic | low | standing → standing |
| `recover` | basic | medium | any → standing |
| `arm_wave` | happy, dance | low | standing → standing |
| `body_sway` | elegant, dance | low | standing → standing |
| `step_forward` | power, dance | low | standing → standing |
| `step_backward` | power, dance | low | standing → standing |
| `turn_left` | elegant, dance | medium | standing → standing |
| `turn_right` | elegant, dance | medium | standing → standing |
| `squat` | power, dance | high | standing → low_pose |

---

## Execution Result Structure

Every backend returns a structured `ExecutionResult` (never raw strings):

```python
@dataclass
class ExecutionResult:
    status: str              # "success" or "failed"
    skill: str               # Skill name
    duration: float          # Planned duration
    steps: int = 0           # Environment steps
    reward: float | None = None        # Cumulative reward (future)
    final_obs: dict | None = None      # Final observation (future)
    info: dict = {}          # Backend-specific info
    failure_reason: str | None = None  # Reason on failure
```

---

## Execution Log Structure

Each log entry contains all 11 fields from INTERFACES.md §5:

```json
{
    "index": 0,
    "skill": "stand_ready",
    "duration": 1.0,
    "source": "agent",
    "status": "success",
    "start_time": 0.0,
    "end_time": 1.0,
    "backend_steps": 0,
    "backend_reward": null,
    "failure_reason": null,
    "backend_info": {}
}
```

---

## Testing

```bash
# Run all tests
pytest -q

# Run specific test files
pytest tests/test_composer.py -q
pytest tests/test_skill_registry.py -q
pytest tests/test_transition_manager.py -q
pytest tests/test_executor.py -q
pytest tests/test_backend.py -q
```

---

## Roadmap

### MVP (current)

- Rule-based Chinese text → skill composition
- 12 registered skills (basic, dance, power, elegant)
- Sequence validation and transition repair (12 rules)
- Dummy backend with configurable failure probability
- Execution recovery on failure
- Structured execution logging and summary statistics

### v0.2 (planned)

- LLM-based composer (`LLMComposer`)
- Motion clip backend (pre-recorded animations)

### v0.3 (planned)

- Trained policy backend integration
- MuJoCo / Gym backend for physics simulation
- Real policy checkpoint loading (`.pt`, `.pth`, `.pkl`, `.npz`)

### v1.0 (planned)

- Isaac Lab backend
- TextOp backend integration
- GR00T foundation model backend
- Real humanoid robot backend

---

## License

[License to be determined]
