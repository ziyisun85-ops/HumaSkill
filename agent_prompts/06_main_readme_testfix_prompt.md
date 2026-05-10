# HumaSkill — Task 06: Main, Logging, README Finalization, and Integration Fixes

## Pre-Flight (READ FIRST)

Before writing any code, read these files in full:

- `PROJECT_PLAN.md` — project goals, system flow, MVP boundary, project structure
- `INTERFACES.md` — **binding contract for all agents** (especially §4 ExecutionResult, §5 Execution Log Item, §12 Required CLI Commands, §13 General Constraints)
- `TASKS.md` — task breakdown (especially Task 06)
- `ACCEPTANCE_CHECKLIST.md` — full acceptance criteria
- `TEST_PLAN.md` — all test cases (especially `test_executor.py` and `test_backend.py` sections)

---

## Task Goal

**This is the integration task — it wires together everything from Tasks 01–05 into a working end-to-end system.** You will implement the CLI entry point, execution logging, summary statistics, a demo script, and finalize the README. You will also fix any integration issues discovered across all modules.

The completed system must support this exact CLI invocation:

```bash
python -m humaskill.main \
  --text "跳一段 12 秒的欢快机器人舞蹈" \
  --duration 12 \
  --seed 42 \
  --fail-prob 0.1 \
  --backend dummy \
  --output logs/demo_log.json
```

And this must produce: structured JSON logs at the output path, a printed summary to stdout, and zero errors.

---

## Allowed Files

You may edit **only** the following files:

### New Implementation Files
| File | Action |
|---|---|
| `humaskill/main.py` | **Create/Implement** — argparse CLI entry point |
| `humaskill/logging_utils/execution_logger.py` | **Create/Implement** — JSON log saving |
| `humaskill/logging_utils/summary.py` | **Create/Implement** — summary statistics |
| `scripts/run_demo.py` | **Create/Implement** — demo script |

### Finalization
| File | Action |
|---|---|
| `README.md` | **Rewrite** — complete project documentation |

### Integration Fixes (only if needed to make the pipeline work)
| File | Action |
|---|---|
| `humaskill/__init__.py` | **May edit** — re-exports if needed |
| `humaskill/composer/__init__.py` | **May edit** — re-exports if needed |
| `humaskill/skills/__init__.py` | **May edit** — re-exports if needed |
| `humaskill/harness/__init__.py` | **May edit** — re-exports if needed |
| `humaskill/backends/__init__.py` | **May edit** — re-exports if needed |
| `humaskill/logging_utils/__init__.py` | **May edit** — re-exports |
| `humaskill/utils/__init__.py` | **May edit** — re-exports if needed |
| `humaskill/harness/skill_executor.py` | **May edit** — integration fixes only |
| `humaskill/harness/transition_manager.py` | **May edit** — integration fixes only |
| `humaskill/harness/sequence_validator.py` | **May edit** — integration fixes only |
| `humaskill/backends/dummy_backend.py` | **May edit** — integration fixes only |
| `humaskill/composer/rule_based_composer.py` | **May edit** — integration fixes only |
| `humaskill/skills/skill_registry.py` | **May edit** — integration fixes only |
| `tests/test_executor.py` | **May edit** — integration fixes only |
| `tests/test_backend.py` | **May edit** — integration fixes only |
| `tests/test_composer.py` | **May edit** — integration fixes only |
| `tests/test_skill_registry.py` | **May edit** — integration fixes only |
| `tests/test_transition_manager.py` | **May edit** — integration fixes only |

**DO NOT edit these files:**
- `PROJECT_PLAN.md`
- `INTERFACES.md`
- `TASKS.md`
- `ACCEPTANCE_CHECKLIST.md`
- `TEST_PLAN.md`
- `DEVELOPMENT_ORDER.md`
- `AGENT_ASSIGNMENTS.md`
- `configs/skills.yaml`
- `configs/default_config.yaml`
- `requirements.txt`
- `pyproject.toml`
- `examples/*`
- Any file not explicitly listed above

If you discover a bug in a restricted file, report it in your completion summary — do NOT fix it directly.

---

## Interfaces (Binding Contract)

All interfaces below come from `INTERFACES.md` and MUST be followed exactly.

### ExecutionResult (INTERFACES.md §4)

The backend returns `ExecutionResult` — **never raw strings**. The executor processes `ExecutionResult.status` — **never raw result strings**.

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class ExecutionResult:
    status: str          # "success" or "failed" ONLY
    skill: str
    duration: float
    steps: int = 0
    reward: float | None = None
    final_obs: dict[str, Any] | None = None
    info: dict[str, Any] = field(default_factory=dict)
    failure_reason: str | None = None
```

### Execution Log Item (INTERFACES.md §5)

Every log item saved by `execution_logger.py` MUST contain ALL of these fields:

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

**Rules:**
- `start_time` and `end_time` use planned time accumulation (cumulative sum of durations)
- `status` comes from `ExecutionResult.status` — string `"success"` or `"failed"`
- `backend_steps` comes from `ExecutionResult.steps`
- `backend_reward` comes from `ExecutionResult.reward`
- `failure_reason` comes from `ExecutionResult.failure_reason`
- `backend_info` comes from `ExecutionResult.info`

### Required CLI Commands (INTERFACES.md §12)

```bash
python scripts/validate_skills.py
python -m humaskill.main --text "跳一段 12 秒的欢快机器人舞蹈" --duration 12 --seed 42 --fail-prob 0.1 --backend dummy --output logs/demo_log.json
pytest -q
```

All three MUST succeed.

### General Constraints (INTERFACES.md §13)

- Python 3.10+
- Dependencies: PyYAML, pytest only
- Backend returns `ExecutionResult`, never raw strings
- Executor logs use `status`, never raw result strings
- Tests must not assume backend returns raw strings

---

## Detailed Requirements

### 1. `humaskill/main.py` — CLI Entry Point

#### Architecture

`main.py` MUST wire together the full pipeline:

```
User CLI args → Composer → SequenceValidator → TransitionManager → SkillExecutor → ExecutionLogger → Summary → Print to stdout
```

#### argparse CLI

| Argument | Type | Required | Default | Description |
|---|---|---|---|---|
| `--text` | `str` | Yes | — | Natural language instruction (Chinese) |
| `--duration` | `float` | Yes | — | Target total duration in seconds |
| `--seed` | `int` | No | `42` | Random seed for reproducibility |
| `--fail-prob` | `float` | No | `0.1` | Probability of execution failure (0.0–1.0) |
| `--backend` | `str` | No | `"dummy"` | Backend name (`"dummy"` in MVP) |
| `--output` | `str` | No | `None` | Path to save execution logs as JSON (if provided) |

#### Pipeline Logic

```python
def main():
    args = parse_args()

    # 1. Load skill registry
    registry = load_registry("configs/skills.yaml")

    # 2. Compose raw sequence
    composer = RuleBasedDanceComposer(registry)
    raw_sequence = composer.compose(args.text, args.duration, args.seed)

    # 3. Validate sequence
    validator = SequenceValidator(registry)
    validator.validate(raw_sequence)

    # 4. Repair transitions
    transition_mgr = TransitionManager(registry)
    repaired_sequence = transition_mgr.repair(raw_sequence)

    # 5. Execute
    backend = create_backend(args.backend, args.fail_prob, args.seed)  # DummyDanceBackend
    executor = SkillExecutor(backend, registry)
    logs = executor.execute(repaired_sequence)

    # 6. Generate summary
    summary = generate_summary(logs)

    # 7. Save logs if --output specified
    if args.output:
        save_execution_log(logs, summary, args.output)

    # 8. Print summary to stdout
    print_summary(summary)
```

#### `create_backend()` dispatch

Only `"dummy"` is implemented in MVP. All other backend names raise `ValueError` with a clear message.

```python
def create_backend(name: str, fail_prob: float, seed: int) -> BaseBackend:
    if name == "dummy":
        from humaskill.backends.dummy_backend import DummyDanceBackend
        return DummyDanceBackend(fail_prob=fail_prob, seed=seed)
    else:
        raise ValueError(f"Unknown backend: {name!r}. Supported: 'dummy'")
```

#### Output

When `--output` is provided, save a JSON file with this structure:

```json
{
    "request": {
        "text": "跳一段 12 秒的欢快机器人舞蹈",
        "duration": 12.0,
        "seed": 42,
        "fail_prob": 0.1,
        "backend": "dummy"
    },
    "sequence": [...],
    "logs": [...],
    "summary": {...}
}
```

When `--output` is NOT provided, skip file saving and only print summary to stdout.

#### Summary Printed to stdout

Print a clean summary including at minimum:
- Request text and total duration
- Total items in sequence
- Success count / failed count / recover count
- Skill breakdown (per-skill execution counts)
- Total time breakdown
- Any warnings (e.g., recoveries triggered)

Use the printing utilities from `humaskill.utils.printing` for formatting.

#### `__main__` guard

```python
if __name__ == "__main__":
    main()
```

### 2. `humaskill/logging_utils/execution_logger.py` — Execution Log Saving

#### Function: `save_execution_log(logs: list[dict], summary: dict, output_path: str) -> None`

Saves execution logs as a structured JSON file. Also stores the request metadata and summary.

#### Function: `build_log_item(index: int, item: dict, result: ExecutionResult, start_time: float, end_time: float) -> dict`

Builds a single log entry from an executed sequence item and its `ExecutionResult`. Returns a dict matching INTERFACES.md §5 exactly:

```python
{
    "index": index,
    "skill": result.skill,
    "duration": result.duration,
    "source": item["source"],
    "status": result.status,
    "start_time": start_time,
    "end_time": end_time,
    "backend_steps": result.steps,
    "backend_reward": result.reward,
    "failure_reason": result.failure_reason,
    "backend_info": result.info
}
```

**Every field must be present in the output.** Fields that don't apply (e.g., `backend_reward` when the backend doesn't provide one) should use `None`, not be omitted.

#### Integration with SkillExecutor

The executor (from Task 05) produces a list of log dicts. The `execution_logger.py` module provides `save_execution_log()` to persist those logs to disk as JSON. Do not duplicate logging logic — the executor owns execution, the logger owns serialization.

If the executor's log items are missing fields that INTERFACES.md §5 requires, fix the executor to include them. This is an integration fix covered under §7 below.

### 3. `humaskill/logging_utils/summary.py` — Summary Statistics

#### Function: `generate_summary(logs: list[dict]) -> dict`

Computes aggregate statistics from execution logs:

```python
{
    "total_duration": <float>,       # Sum of all item durations from logs
    "total_items": <int>,            # Total number of log entries
    "success_count": <int>,          # Count of status == "success"
    "failed_count": <int>,           # Count of status == "failed"
    "recover_count": <int>,          # Count of source == "recovery_inserted"
    "skill_breakdown": {             # Per-skill counts
        "arm_wave": 2,
        "body_sway": 1,
        "stand_ready": 1,
        "stand_stable": 1,
        "final_pose": 1
    },
    "recovery_triggered": <bool>,    # True if any recover_count > 0
    "pipeline_time": <float>         # Same as total_duration (the wall-clock time of the full sequence)
}
```

#### Field Semantics

- `total_duration`: Sum of `duration` field from all log entries.
- `total_items`: `len(logs)`.
- `success_count`: Count of entries where `status == "success"`.
- `failed_count`: Count of entries where `status == "failed"`.
- `recover_count`: Count of entries where `source == "recovery_inserted"`.
- `skill_breakdown`: `dict[str, int]` mapping each unique `skill` name to its occurrence count.
- `recovery_triggered`: `True` if `recover_count > 0`, else `False`.

#### Function: `print_summary(summary: dict) -> None`

Prints the summary in a human-readable format to stdout. Use the printing utilities from `humaskill.utils.printing`. Include:
- A header line
- Request info (text, duration)
- Success/Failed/Recover counts
- Skill breakdown table
- Total pipeline time

### 4. `scripts/run_demo.py` — Demo Script

A convenience script that runs the full pipeline with demo parameters and saves output. It should:

1. Set the working directory to the project root (resolve relative to the script location).
2. Run the equivalent of:
   ```
   python -m humaskill.main --text "跳一段 12 秒的欢快机器人舞蹈" --duration 12 --seed 42 --fail-prob 0.1 --backend dummy --output logs/demo_log.json
   ```
3. Can be invoked simply as: `python scripts/run_demo.py`

Implementation approach: either use `subprocess.run()` to invoke `humaskill.main` as a subprocess, or import `humaskill.main` and call its `main()` function programmatically. The latter is preferred (no subprocess overhead, easier to debug).

If using the programmatic approach, use `sys.argv` manipulation or direct function calls. Ensure the `--output` path is resolved correctly relative to the project root.

### 5. `README.md` — Finalize

**Completely rewrite `README.md`** with the following sections:

#### Title and Tagline

```
# HumaSkill

Skill-level composition and execution harness for language-guided humanoid motion composition.
```

#### Project Positioning

Explain that HumaSkill is a **skill-level composition harness** — it sits above low-level motion generation and handles:
- Natural language → skill sequence composition
- Sequence validation
- Transition repair (pose matching, risk-based safety inserts, duration clamping)
- Execution monitoring with automatic recovery on failure
- Structured logging and summary statistics

It does NOT generate motion trajectories itself — that's the backends' job.

#### Relationship with TextOp

```
HumaSkill is a skill-level composition and execution harness.
It composes skill sequences, repairs transitions, monitors execution,
and handles recovery.

TextOp and similar text-to-motion systems can later be integrated
as backends into HumaSkill. The TextOpBackend placeholder class
already exists in humaskill/backends/textop_backend.py, reserving
the integration point for future use.
```

#### Trained Skill Policies

```
HumaSkill handles high-level skill composition, transition repair,
execution monitoring, and recovery.

Pre-trained skill policies handle low-level control for individual skills.

TrainedPolicyBackend (placeholder) connects HumaSkill to pre-trained
skill policies loaded from checkpoints (.pt, .pth, .pkl, .npz).

The policies/ directory exists from day one:
  policies/
    base_policy.py       — BaseSkillPolicy ABC
    policy_registry.py   — PolicyRegistry for lookup
    policy_adapter.py    — PolicyAdapter (obs conversion)
    checkpoint_loader.py — CheckpointLoader (.pt/.pth/.pkl/.npz)
```

#### MuJoCo / Gym Backend

```
The MujocoGymBackend placeholder reserves the integration point
for MuJoCo or Gymnasium-based simulation environments.

Future: execute HumaSkill skill sequences in physics simulation,
producing trajectories with joint positions, torques, or velocity commands.
```

#### Installation

```bash
# Clone
git clone <repo-url>
cd HumaSkill

# Install dependencies
pip install -r requirements.txt

# Verify skill configuration
python scripts/validate_skills.py
```

Dependencies: Python 3.10+, PyYAML, pytest.

#### Usage

```bash
# Run with demo parameters
python -m humaskill.main \
  --text "跳一段 12 秒的欢快机器人舞蹈" \
  --duration 12 \
  --seed 42 \
  --fail-prob 0.1 \
  --backend dummy \
  --output logs/demo_log.json

# Or use the demo script
python scripts/run_demo.py
```

#### Supported Backends

| Backend | Status | Description |
|---|---|---|
| `dummy` | Implemented (MVP) | Rule-based dummy execution with configurable failure probability |
| `motion_clip` | Placeholder | Pre-recorded motion clip playback |
| `trained_policy` | Placeholder | Pre-trained skill policy inference |
| `mujoco_gym` | Placeholder | MuJoCo / Gymnasium physics simulation |
| `isaaclab` | Placeholder | NVIDIA Isaac Lab simulation |
| `textop` | Placeholder | Text-to-motion generation |
| `groot` | Placeholder | GR00T foundation model |

#### Project Structure

Show the directory tree from `PROJECT_PLAN.md` (summarized — include the key directories and their purpose).

#### CLI Reference

```
usage: python -m humaskill.main [-h] --text TEXT --duration DURATION
                                [--seed SEED] [--fail-prob FAIL_PROB]
                                [--backend BACKEND] [--output OUTPUT]

arguments:
  --text TEXT          Natural language instruction (Chinese)
  --duration DURATION  Target total duration in seconds
  --seed SEED          Random seed (default: 42)
  --fail-prob FAIL_PROB Failure probability 0.0–1.0 (default: 0.1)
  --backend BACKEND    Execution backend (default: dummy)
  --output OUTPUT      Path to save execution logs as JSON
```

#### Roadmap

```
MVP (current):
  - Rule-based Chinese text → skill composition
  - 12 registered skills (basic, dance, power, elegant)
  - Sequence validation and transition repair (12 rules)
  - Dummy backend with configurable failure probability
  - Execution recovery on failure
  - Structured execution logging and summary statistics

v0.2 (planned):
  - LLM-based composer (LLMComposer)
  - Motion clip backend (pre-recorded animations)

v0.3 (planned):
  - Trained policy backend integration
  - MuJoCo / Gym backend for physics simulation
  - Real policy checkpoint loading

v1.0 (planned):
  - Isaac Lab backend
  - TextOp backend integration
  - GR00T foundation model backend
  - Real humanoid robot backend
```

#### Testing

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

### 6. `humaskill/logging_utils/__init__.py` — Re-exports

Update to export:
```python
from humaskill.logging_utils.execution_logger import save_execution_log, build_log_item
from humaskill.logging_utils.summary import generate_summary, print_summary

__all__ = [
    "save_execution_log",
    "build_log_item",
    "generate_summary",
    "print_summary",
]
```

### 7. Integration Fixes

**This task is the glue that makes the full pipeline work.** After implementing the new files, run the full pipeline and fix any issues that prevent it from running correctly.

#### Common Integration Issues to Watch For

1. **Imports**: If module A imports from module B but module B's `__init__.py` doesn't re-export it, fix the `__init__.py`.

2. **Backend returns `ExecutionResult`, not raw strings**: Verify that `DummyDanceBackend.execute()` returns an `ExecutionResult` instance, not a string. If it returns a string, fix it to return the dataclass. Tests must validate `result.status`, not `result == "success"`.

3. **Executor logs use `status`, not raw strings**: Verify the executor (from Task 05) stores `status` as `"success"`/`"failed"` strings in log items. If the executor stores raw `ExecutionResult` objects or raw strings in log items, fix it.

4. **Log items match INTERFACES.md §5**: If log items from the executor are missing `backend_steps`, `backend_reward`, `failure_reason`, or `backend_info` fields, add them. If the executor was implemented before `ExecutionResult` had these fields, update the executor to extract them from the result.

5. **Executor handles `recovery_inserted` items**: After a failed execution and recovery, the executor should insert a `recover` skill item and mark it with `source: "recovery_inserted"`. If the executor doesn't do this, implement it.

6. **`SequenceValidator` existence**: If `SequenceValidator` doesn't exist yet (it's from Task 04), create a minimal implementation or integrate without it. Check whether it's been implemented. If missing, either:
   - Create a minimal `SequenceValidator` that validates each item has `skill` (str) and `duration` (float), raising `InvalidSequenceError` on failure.
   - Skip validation and note in the summary.

7. **`TransitionManager` interface**: Verify that `TransitionManager.repair()` takes raw sequence items `[{"skill": str, "duration": float}]` and returns repaired items `[{"skill": str, "duration": float, "source": str}]`.

8. **`SkillExecutor` constructor**: Verify signature — `SkillExecutor(backend: BaseBackend, registry: SkillRegistry)` is the expected interface. If the actual constructor differs, adapt `main.py` accordingly.

9. **Path resolution**: `configs/skills.yaml` path in `main.py` should be resolved relative to the project root, not the current working directory. Use `pathlib.Path(__file__).resolve().parent.parent / "configs" / "skills.yaml"` or a similar relative resolution.

10. **`fail_prob` parameter**: `DummyDanceBackend` must accept `fail_prob` in its constructor. If it uses a different parameter name, adapt `main.py`.

#### Integration Fix Protocol

For each issue found:
1. Identify which file is causing the problem and confirm it's in the allowed list.
2. Make the minimal fix — do not refactor or rewrite.
3. Re-run the pipeline to verify the fix.
4. Document the issue in your completion summary.

**If a fix requires editing a restricted file** (not in the allowed list), do NOT edit it. Instead, document the issue clearly in your completion summary so the project maintainer can address it.

---

## Tests

This task does NOT create a new test file. Instead, it requires that ALL EXISTING tests pass:

```bash
pytest -q
```

This runs all 5 test files:
- `tests/test_composer.py`
- `tests/test_skill_registry.py`
- `tests/test_transition_manager.py`
- `tests/test_executor.py`
- `tests/test_backend.py`

### If Tests Fail

1. Identify the failing test.
2. Determine if the test is testing the right thing but the implementation is wrong → fix the implementation.
3. Determine if the test itself has a bug (e.g., assuming backend returns raw strings) → fix the test.
4. **Do not weaken tests to make them pass.** If a test is correct but the implementation is wrong, fix the implementation.

### Test Constraints from INTERFACES.md §13

> Tests must not assume backend returns raw strings.

All test assertions about backend results must use `result.status` or `result.skill` — never `result == "success"` or string comparison on the result object. Fix any tests that violate this rule.

---

## Acceptance Criteria

Before declaring this task complete, verify ALL of the following:

### CLI
- [ ] `python -m humaskill.main --text "..." --duration 12 --seed 42 --fail-prob 0.1 --backend dummy --output logs/demo_log.json` runs without error
- [ ] `logs/demo_log.json` is created with the correct structure (`request`, `sequence`, `logs`, `summary`)
- [ ] Each log item in `logs` has ALL fields from INTERFACES.md §5
- [ ] Summary is printed to stdout with clear formatting

### Logging
- [ ] `execution_logger.py` saves JSON with the full structure
- [ ] `save_execution_log()` accepts `logs: list[dict]`, `summary: dict`, `output_path: str`
- [ ] `build_log_item()` produces dicts matching INTERFACES.md §5 exactly
- [ ] No fields are omitted from log items (use `None` for unavailable fields)

### Summary
- [ ] `generate_summary()` returns dict with all required fields: `total_duration`, `total_items`, `success_count`, `failed_count`, `recover_count`, `skill_breakdown`, `recovery_triggered`, `pipeline_time`
- [ ] `skill_breakdown` is a `dict[str, int]` of per-skill counts
- [ ] `recovery_triggered` is `True` when `recover_count > 0`

### README
- [ ] Explains project positioning (skill-level composition harness)
- [ ] Explains relationship with TextOp
- [ ] Explains relationship with trained skill policies
- [ ] Documents MuJoCo / Gym backend placeholder
- [ ] Includes installation instructions
- [ ] Includes usage example with the demo command
- [ ] Includes CLI reference
- [ ] Includes roadmap
- [ ] Includes testing instructions

### Scripts
- [ ] `scripts/validate_skills.py` runs successfully (implemented in Task 02; must still work)
- [ ] `scripts/run_demo.py` runs successfully (implemented in this task)

### Tests
- [ ] `pytest -q` passes ALL tests with zero failures
- [ ] No test assumes backend returns raw strings (check `test_backend.py` and `test_executor.py`)

### Integration
- [ ] Full pipeline runs end-to-end: compose → validate → repair → execute → log → summarize
- [ ] Error handling works: missing `--text` or `--duration` shows argparse error
- [ ] `--output` is optional (omitting it skips file save but still prints summary)

---

## General Constraints (Mandatory)

1. **Follow INTERFACES.md strictly.** Every interface in INTERFACES.md is a binding contract. Do not deviate — not in field names, not in log item structure, not in return types.

2. **Only edit files explicitly allowed.** The allowed list above is definitive. If you discover an issue in a restricted file, report it — do not fix it.

3. **Use Python 3.10+.** Use `str | None` syntax, not `Optional[str]`. Use `list[dict]`, not `List[dict]`.

4. **Use only PyYAML and pytest.** No other third-party dependencies. No numpy, no requests, no click, no tqdm, no rich. Standard library only for main/logging/summary/scripts.

5. **Backend returns ExecutionResult.** This is non-negotiable. Backend never returns raw strings. Executor never treats result as a string. Tests never compare result to strings.

6. **Executor logs use `status`.** Log items use `"success"` / `"failed"` strings, never raw `ExecutionResult` objects.

7. **Tests must not assume backend returns raw strings.** Tests validate `result.status`, `result.skill`, etc. — not `result == "success"`.

8. **Handle paths portably.** Use `pathlib.Path` for path operations. Resolve config paths relative to the package, not cwd. The project must work on both Windows and Linux.

9. **Use docstrings.** Every public function and class must have a docstring.

10. **Use clear error messages.** Include relevant context (skill name, backend name, file path) in all error messages.

11. **Integration fixes must be minimal.** Do not refactor or rewrite code from previous tasks. Fix only what's broken.

12. **If you believe an interface is wrong**, do NOT change it. Report it in your completion summary.

---

## Verification

After implementation, run from the project root:

```bash
# 1. Install dependencies (if not already installed)
pip install -r requirements.txt

# 2. Validate skill configuration (Task 02 — must still work)
python scripts/validate_skills.py

# 3. Run the demo (implemented in this task)
python scripts/run_demo.py

# 4. Run the full pipeline directly
python -m humaskill.main \
  --text "跳一段 12 秒的欢快机器人舞蹈" \
  --duration 12 \
  --seed 42 \
  --fail-prob 0.1 \
  --backend dummy \
  --output logs/demo_log.json

# 5. Verify the log file was created and has the correct structure
python -c "
import json
with open('logs/demo_log.json') as f:
    data = json.load(f)
assert 'request' in data
assert 'sequence' in data
assert 'logs' in data
assert 'summary' in data
log = data['logs'][0]
required = ['index','skill','duration','source','status','start_time','end_time','backend_steps','backend_reward','failure_reason','backend_info']
for field in required:
    assert field in log, f'Missing field: {field}'
print('Log structure: OK')
print('Summary:', json.dumps(data['summary'], indent=2, ensure_ascii=False))
"

# 6. Run ALL tests
pytest -q

# 7. Verify the sequence output
python -m humaskill.main \
  --text "跳一段 12 秒的欢快机器人舞蹈" \
  --duration 12 \
  --seed 42 \
  --fail-prob 0 \
  --backend dummy

# (should succeed with zero failures, all success statuses)
```

All commands must succeed with zero errors.

---

## Completion Summary

When done, provide a summary including:
1. Files created and modified
2. Any integration issues found and how they were fixed
3. Any issues in restricted files that were NOT fixed (reported for maintainer)
4. Test results (`pytest -q` output)
5. Demo verification (the log file structure)
