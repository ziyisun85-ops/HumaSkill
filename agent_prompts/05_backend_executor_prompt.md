# HumaSkill — Task 05: Backend, Policy Interface, and Executor

## Pre-Flight (READ FIRST)

Before writing any code, read these files in full:

- `PROJECT_PLAN.md` — project goals, system flow, module responsibilities, MVP boundary
- `INTERFACES.md` — binding contract for all agents (especially Section 4: ExecutionResult, Section 6: Backend Interface, Section 8: Policy Interfaces, Section 10: Required Exceptions, Section 5: Execution Log Item)
- `TASKS.md` — task breakdown (especially Task 05)
- `ACCEPTANCE_CHECKLIST.md` — acceptance criteria
- `TEST_PLAN.md` — test cases (especially `test_backend.py` and `test_executor.py` sections)

---

## Task Goal

Implement the HumaSkill **backends** (BaseBackend ABC, DummyDanceBackend, 6 placeholder backends), **policies** (BaseSkillPolicy ABC, PolicyRegistry, PolicyAdapter placeholder, CheckpointLoader placeholder), and **SkillExecutor** (with recovery logic). Plus two test files.

Fifteen files total:

**Backends (8 files):**
1. `BaseBackend` — abstract base class with `execute(skill_name, duration) -> ExecutionResult`
2. `DummyDanceBackend` — MVP backend with `fail_prob` support, returns `ExecutionResult`
3. `MotionClipBackend` — placeholder
4. `TrainedPolicyBackend` — placeholder
5. `MujocoGymBackend` — placeholder
6. `IsaacLabBackend` — placeholder
7. `TextOpBackend` — placeholder
8. `GrootBackend` — placeholder

**Policies (4 files):**
9. `BaseSkillPolicy` — abstract base class: `reset()`, `act()`
10. `PolicyRegistry` — maps skill names to policy instances
11. `PolicyAdapter` — placeholder for observation conversion
12. `CheckpointLoader` — placeholder for loading `.pt/.pth/.pkl/.npz` checkpoints

**Executor (1 file):**
13. `SkillExecutor` — executes repaired sequences through a backend, handles recovery on `failed`

**Tests (2 files):**
14. `test_backend.py` — 8 test cases for backends and ExecutionResult
15. `test_executor.py` — 6 test cases for executor and recovery logic

---

## Allowed Files

You may ONLY edit these files:

```
humaskill/backends/__init__.py            (add re-exports)
humaskill/backends/base_backend.py        (create/implement)
humaskill/backends/dummy_backend.py       (create/implement)
humaskill/backends/motion_clip_backend.py (create/implement placeholder)
humaskill/backends/trained_policy_backend.py (create/implement placeholder)
humaskill/backends/mujoco_gym_backend.py  (create/implement placeholder)
humaskill/backends/isaaclab_backend.py    (create/implement placeholder)
humaskill/backends/textop_backend.py      (create/implement placeholder)
humaskill/backends/groot_backend.py       (create/implement placeholder)

humaskill/policies/__init__.py            (add re-exports)
humaskill/policies/base_policy.py         (create/implement)
humaskill/policies/policy_registry.py     (create/implement)
humaskill/policies/policy_adapter.py      (create/implement placeholder)
humaskill/policies/checkpoint_loader.py   (create/implement placeholder)

humaskill/harness/skill_executor.py       (create/implement)

tests/test_backend.py                     (create/implement)
tests/test_executor.py                    (create/implement)
```

DO NOT edit any other files. DO NOT modify `PROJECT_PLAN.md`, `INTERFACES.md`, `TASKS.md`, `ACCEPTANCE_CHECKLIST.md`, `TEST_PLAN.md`, or any file outside this list.

The following modules already exist from prior tasks and should be imported (do not modify them):

- `humaskill.utils.errors` — all custom exceptions (incl. `BackendExecutionError`, `PolicyLoadError`)
- `humaskill.skills.skill_registry` — `SkillRegistry`
- `humaskill.skills.skill_info` — `SkillInfo` dataclass
- `humaskill.harness.transition_manager` — `TransitionManager` (may be imported if needed for context)
- `humaskill.harness.sequence_validator` — `SequenceValidator`

---

## Interfaces to Follow

Follow `INTERFACES.md` strictly. This is the binding contract.

### 1. ExecutionResult Dataclass (INTERFACES.md §4)

Implement in `humaskill/backends/base_backend.py`:

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

**Allowed `status` values: ONLY `"success"` or `"failed"`.**

**MVP (DummyBackend) fills:** `status`, `skill`, `duration`, `steps`, `failure_reason`, `info`

**Field semantics:**

| Field | Type | Description |
|---|---|---|
| `status` | `str` | `"success"` or `"failed"` |
| `skill` | `str` | Skill name that was executed |
| `duration` | `float` | Planned execution duration |
| `steps` | `int` | Backend environment step count |
| `reward` | `float \| None` | Cumulative reward (future backends) |
| `final_obs` | `dict \| None` | Final observation after execution (future) |
| `info` | `dict` | Backend-specific extra information |
| `failure_reason` | `str \| None` | Reason for failure, if status is `"failed"` |

### 2. BaseBackend ABC (INTERFACES.md §6)

Implement in `humaskill/backends/base_backend.py`:

```python
from abc import ABC, abstractmethod


class BaseBackend(ABC):
    @abstractmethod
    def execute(self, skill_name: str, duration: float) -> ExecutionResult:
        """Execute a skill and return a structured execution result.

        Args:
            skill_name: Name of the skill to execute.
            duration: Planned execution duration in seconds.

        Returns:
            ExecutionResult with status, skill name, duration, and backend data.
        """
        raise NotImplementedError
```

**Every backend MUST return `ExecutionResult`.**
**`ExecutionResult.status` MUST be `"success"` or `"failed"`.**
**Backends MUST NOT return raw strings.**

### 3. DummyDanceBackend (dummy_backend.py)

```python
class DummyDanceBackend(BaseBackend):
    """MVP dummy backend that simulates skill execution with configurable failure rate.

    Uses a seeded random number generator so that fail_prob + seed produce
    reproducible results. When fail_prob is 0.0, all executions succeed.
    When fail_prob is 1.0, all executions fail.
    """

    def __init__(self, fail_prob: float = 0.0, seed: int | None = None):
        """Initialize the dummy backend.

        Args:
            fail_prob: Probability of execution failure (0.0 to 1.0).
            seed: Random seed for reproducible failure patterns.
        """
```

**`execute(skill_name, duration)` logic:**

1. Use `random.Random(seed)` for reproducibility — same seed + same fail_prob produce identical results.
2. Generate a random float in `[0.0, 1.0)`. If < fail_prob, the execution fails.
3. If **success**:
   - `status = "success"`
   - `steps = max(1, int(duration * 10))` (simulated step count, at least 1)
   - `failure_reason = None`
   - `info = {"backend": "dummy", "simulated": True}`
4. If **failed**:
   - `status = "failed"`
   - `steps = 0`
   - `failure_reason = "Simulated dummy backend failure"`
   - `info = {"backend": "dummy", "simulated": True}`
5. Always set `skill = skill_name`, `duration = duration`.
6. `reward` and `final_obs` remain `None` (MVP does not simulate rewards/observations).

**Edge cases:**
- `fail_prob` outside `[0.0, 1.0]` → raise `ValueError` with a clear message.
- `skill_name` empty string → raise `ValueError`.
- `duration <= 0` → raise `ValueError`.

### 4. Placeholder Backends (6 files)

Each placeholder backend inherits from `BaseBackend` and raises `NotImplementedError` with a descriptive message. Each must be a class, not a module-level stub.

```python
# humaskill/backends/motion_clip_backend.py
from humaskill.backends.base_backend import BaseBackend, ExecutionResult


class MotionClipBackend(BaseBackend):
    """Placeholder for future motion-clip-based skill execution.

    This backend will execute skills by playing back pre-recorded
    motion capture clips. Not implemented in the MVP.
    """

    def execute(self, skill_name: str, duration: float) -> ExecutionResult:
        raise NotImplementedError("MotionClipBackend is a placeholder for future implementation")
```

Repeat this pattern for all six:
- `MotionClipBackend` — `motion_clip_backend.py`
- `TrainedPolicyBackend` — `trained_policy_backend.py`
- `MujocoGymBackend` — `mujoco_gym_backend.py`
- `IsaacLabBackend` — `isaaclab_backend.py`
- `TextOpBackend` — `textop_backend.py`
- `GrootBackend` — `groot_backend.py`

Each must have a distinct, descriptive docstring. Each must explicitly raise `NotImplementedError`.

### 5. BaseSkillPolicy ABC (INTERFACES.md §8)

Implement in `humaskill/policies/base_policy.py`:

```python
from abc import ABC, abstractmethod
from typing import Any


class BaseSkillPolicy(ABC):
    """Abstract base for pre-trained skill policies.

    Pre-trained skill policies handle low-level control for individual skills.
    HumaSkill handles high-level composition, transition repair, and recovery.
    """

    @abstractmethod
    def reset(self, skill_name: str, skill_param: dict | None = None) -> None:
        """Reset internal policy state before executing a skill.

        Args:
            skill_name: Name of the skill to execute.
            skill_param: Optional skill-specific parameters.
        """
        raise NotImplementedError

    @abstractmethod
    def act(self, obs: dict[str, Any]) -> Any:
        """Return low-level action from policy observation.

        Args:
            obs: Environment observation dictionary.

        Returns:
            Action in the format expected by the backend environment.
        """
        raise NotImplementedError
```

### 6. PolicyRegistry (INTERFACES.md §8)

Implement in `humaskill/policies/policy_registry.py`:

```python
class PolicyRegistry:
    """Registry that maps skill names to BaseSkillPolicy instances.

    Methods:
        register(skill_name: str, policy: BaseSkillPolicy) -> None
        get(skill_name: str) -> BaseSkillPolicy
        has(skill_name: str) -> bool
        all_names() -> list[str]
    """

    def __init__(self):
        self._policies: dict[str, BaseSkillPolicy] = {}

    def register(self, skill_name: str, policy: BaseSkillPolicy) -> None:
        """Register a skill policy for a given skill name.

        Args:
            skill_name: Skill name to register the policy for.
            policy: BaseSkillPolicy instance.

        Raises:
            ValueError: If skill_name is already registered.
        """
        raise NotImplementedError  # Replace with implementation

    def get(self, skill_name: str) -> BaseSkillPolicy:
        """Retrieve the policy for a given skill name.

        Args:
            skill_name: Skill name to look up.

        Returns:
            BaseSkillPolicy instance.

        Raises:
            KeyError: If skill_name is not registered.
        """
        raise NotImplementedError  # Replace with implementation

    def has(self, skill_name: str) -> bool:
        """Check if a skill name has a registered policy."""
        raise NotImplementedError  # Replace with implementation

    def all_names(self) -> list[str]:
        """Return all registered skill names."""
        raise NotImplementedError  # Replace with implementation
```

**Requirements:**
- `register()` raises `ValueError` (not `KeyError`) if the name is already registered.
- `get()` raises `KeyError` if the name is not found.
- `has()` returns `True/False`.
- `all_names()` returns a list of strings.

### 7. PolicyAdapter Placeholder (policy_adapter.py)

```python
from humaskill.policies.base_policy import BaseSkillPolicy


class PolicyAdapter:
    """Placeholder for future observation conversion.

    Converts environment observations into the format expected by
    a specific pre-trained skill policy. Not implemented in the MVP.
    """

    def build_policy_obs(self, skill_name: str, env_obs: dict) -> dict:
        """Convert environment observation to policy observation.

        Args:
            skill_name: Skill being executed.
            env_obs: Raw environment observation.

        Returns:
            Observation dict formatted for the skill policy.
        """
        raise NotImplementedError("PolicyAdapter is a placeholder for future implementation")
```

### 8. CheckpointLoader Placeholder (checkpoint_loader.py)

```python
from humaskill.policies.base_policy import BaseSkillPolicy


class CheckpointLoader:
    """Placeholder for future checkpoint loading.

    Loads pre-trained skill policies from checkpoint files
    ('.pt', '.pth', '.pkl', '.npz'). Not implemented in the MVP.
    """

    def load(self, checkpoint_path: str) -> BaseSkillPolicy:
        """Load a pretrained skill policy from checkpoint.

        Args:
            checkpoint_path: Path to the checkpoint file.

        Returns:
            Loaded BaseSkillPolicy instance.
        """
        raise NotImplementedError("CheckpointLoader is a placeholder for future implementation")
```

### 9. SkillExecutor (harness/skill_executor.py)

```python
class SkillExecutor:
    """Executes a repaired skill sequence through a backend with recovery on failure.

    When a backend returns ExecutionResult with status "failed", the executor
    inserts a "recover" skill before the failed skill and retries the failed skill
    once. The recover skill has source="recovery_inserted". Logs use structured
    ExecutionResult fields — never raw strings.
    """

    def __init__(self, backend: BaseBackend, registry: SkillRegistry):
        """Initialize the executor.

        Args:
            backend: Backend instance that executes individual skills.
            registry: SkillRegistry for looking up skill metadata (e.g., default durations).
        """
```

**`execute_sequence(sequence: list[dict])` → tuple[list[dict], dict]:**

Input: a list of repaired sequence items. Each item is a dict with `skill`, `duration`, `source`.
Returns: `(execution_logs, summary)`.

**Execution logic:**

1. Iterate through the sequence in order.
2. For each item, call `backend.execute(skill_name=item["skill"], duration=item["duration"])`.
3. Build a log entry from the ExecutionResult. Log entries MUST match this structure:

```python
{
    "index": <int>,          # 0-based execution index
    "skill": <str>,
    "duration": <float>,
    "source": <str>,         # from sequence item
    "status": <str>,         # from ExecutionResult.status (NOT raw string)
    "start_time": <float>,   # accumulated planned time
    "end_time": <float>,     # start_time + duration
    "backend_steps": <int>,  # from ExecutionResult.steps
    "backend_reward": <float or None>,  # from ExecutionResult.reward
    "failure_reason": <str or None>,    # from ExecutionResult.failure_reason
    "backend_info": <dict>,  # from ExecutionResult.info
}
```

4. **Track time:** Initialize `current_time = 0.0`. For each item, `start_time = current_time`, then `current_time += duration`, then `end_time = current_time`. No real sleep needed in MVP.

5. **Recovery on failure:** If `ExecutionResult.status == "failed"`:
   - Look up the `recover` skill's default duration from the registry (`registry.get("recover").duration_range` — use the midpoint).
   - Insert a log entry for the `recover` skill with `source = "recovery_inserted"` and `status = "success"`. The `recover` batch itself always succeeds (just call `backend.execute("recover", recover_duration)` — treat the result as info only; the recover log entry always has `status = "success"` since it's a recovery action, not a skill execution).
   - **Alternative approach (simpler):** Call `backend.execute("recover", recover_duration)` and use its result. If the recover itself fails, still log it but with `status = "failed"` and continue to the next item (do not retry recovery).
   - After recovery, retry the failed skill exactly once by calling `backend.execute()` again with the same arguments.
   - If the retry also fails (`status == "failed"`), move on to the next skill in the sequence.
   - Both the original failure and the retry result are logged as separate log entries.
   - Track how many recovery attempts were made for the summary.

6. **Summary:** After all items are processed, return a summary dict:

```python
{
    "total_items": <int>,            # total log entries (including recovery inserts)
    "total_duration": <float>,       # sum of all item durations (original items only, not recover inserts)
    "planned_duration": <float>,     # original planned total (sum of input sequence durations)
    "success_count": <int>,          # log entries with status "success"
    "failed_count": <int>,           # log entries with status "failed"
    "recover_count": <int>,          # number of recovery attempts made
    "backend_name": <str>,           # backend class name (e.g., "DummyDanceBackend")
}
```

**Edge cases:**
- Empty sequence: return `([], summary_with_zeros)` — no crash.
- Missing `recover` skill in registry: raise `UnknownSkillError` with a clear message when recovery is needed.
- `source` field defaults to `"agent"` if missing from the input item (defensive).

**IMPORTANT:** Executor logs use `status`, never raw result strings. Log entries are built from `ExecutionResult` fields, never from string comparisons against raw output. This is a strict requirement from INTERFACES.md §13.

---

## Implementation Requirements

### Dependencies

- Python 3.10+
- `PyYAML` (already used by skill registry)
- `pytest` (for tests)
- Standard library only: `abc`, `random`, `dataclasses`, `typing`

### Code Quality

- Write docstrings for all public classes and methods.
- Use type hints throughout.
- Use clear, descriptive exception messages.
- Handle edge cases: empty sequence, missing `recover` skill, invalid fail_prob, empty skill_name, zero/negative duration.
- Platform-agnostic: no hardcoded Windows or Linux paths.

### Imports in `__init__.py`

Update `humaskill/backends/__init__.py` to export:
```python
from humaskill.backends.base_backend import BaseBackend, ExecutionResult
from humaskill.backends.dummy_backend import DummyDanceBackend
from humaskill.backends.motion_clip_backend import MotionClipBackend
from humaskill.backends.trained_policy_backend import TrainedPolicyBackend
from humaskill.backends.mujoco_gym_backend import MujocoGymBackend
from humaskill.backends.isaaclab_backend import IsaacLabBackend
from humaskill.backends.textop_backend import TextOpBackend
from humaskill.backends.groot_backend import GrootBackend

__all__ = [
    "BaseBackend",
    "ExecutionResult",
    "DummyDanceBackend",
    "MotionClipBackend",
    "TrainedPolicyBackend",
    "MujocoGymBackend",
    "IsaacLabBackend",
    "TextOpBackend",
    "GrootBackend",
]
```

Update `humaskill/policies/__init__.py` to export:
```python
from humaskill.policies.base_policy import BaseSkillPolicy
from humaskill.policies.policy_registry import PolicyRegistry
from humaskill.policies.policy_adapter import PolicyAdapter
from humaskill.policies.checkpoint_loader import CheckpointLoader

__all__ = ["BaseSkillPolicy", "PolicyRegistry", "PolicyAdapter", "CheckpointLoader"]
```

---

## Tests (tests/test_backend.py)

Implement ALL 8 test cases from `TEST_PLAN.md` test_backend section:

| # | Test Name | Description |
|---|-----------|-------------|
| 1 | `test_dummy_backend_returns_execution_result` | `DummyDanceBackend.execute()` returns an `ExecutionResult` instance (not a dict, not a string) |
| 2 | `test_dummy_backend_default_success` | With default `fail_prob=0.0`, execution returns `status == "success"` |
| 3 | `test_fail_prob_causes_failure` | With `fail_prob=1.0`, execution returns `status == "failed"` |
| 4 | `test_same_seed_reproducible` | Same seed + same fail_prob (e.g., 0.5) produces identical results across multiple calls |
| 5 | `test_status_only_success_or_failed` | `ExecutionResult.status` is always exactly `"success"` or `"failed"` — test with various fail_prob values (0.0, 0.5, 1.0) |
| 6 | `test_placeholder_backends_exist` | All 6 placeholders (`MotionClipBackend`, `TrainedPolicyBackend`, `MujocoGymBackend`, `IsaacLabBackend`, `TextOpBackend`, `GrootBackend`) are importable and are subclasses of `BaseBackend`. Each raises `NotImplementedError` on `execute()`. |
| 7 | `test_base_backend_is_abstract` | `BaseBackend` cannot be instantiated directly (raises `TypeError`) |
| 8 | `test_dummy_backend_result_has_correct_skill` | Returned `ExecutionResult.skill` matches the requested skill name. Also verify `duration` matches. |

### Running Tests

```bash
pytest tests/test_backend.py -q -v
```

---

## Tests (tests/test_executor.py)

Implement ALL 6 test cases from `TEST_PLAN.md` test_executor section:

| # | Test Name | Description |
|---|-----------|-------------|
| 1 | `test_execute_repaired_sequence` | Executor runs a complete repaired sequence through backend. Verify: logs is a non-empty list, each log entry has all required fields (`index`, `skill`, `duration`, `source`, `status`, `start_time`, `end_time`, `backend_steps`, `backend_reward`, `failure_reason`, `backend_info`). |
| 2 | `test_failed_triggers_recover` | When backend returns `failed`, executor inserts a `recover` skill and retries. Verify: at least one log entry has `skill == "recover"` and `source == "recovery_inserted"`. Also verify the failed skill appears twice in logs (original attempt + retry). |
| 3 | `test_logs_have_full_structure` | Every log item contains: `index`, `skill`, `duration`, `source`, `status`, `start_time`, `end_time`. Verify all 7 fields are present in every entry. |
| 4 | `test_logs_have_backend_fields` | Every log item contains: `backend_steps`, `backend_reward`, `failure_reason`, `backend_info`. Verify all 4 fields are present in every entry. |
| 5 | `test_summary_fields_correct` | Summary dict has: `total_items`, `total_duration`, `planned_duration`, `success_count`, `failed_count`, `recover_count`, `backend_name`. Verify counts are consistent with the logs. |
| 6 | `test_execute_empty_sequence` | Executing an empty sequence returns empty logs `[]` and a summary with zero/empty values. No crash, no exception. |

### Test Fixtures

Use shared fixtures that load the `SkillRegistry` from `configs/skills.yaml` and create a `DummyDanceBackend` with a known seed:

```python
import pytest
from humaskill.skills.skill_registry import SkillRegistry
from humaskill.backends.dummy_backend import DummyDanceBackend


@pytest.fixture(scope="module")
def registry():
    """Load the skill registry from configs/skills.yaml."""
    from humaskill.skills.skill_registry import SkillRegistry
    reg = SkillRegistry()
    reg.load_yaml("configs/skills.yaml")
    return reg


@pytest.fixture
def dummy_backend():
    """Create a DummyDanceBackend with default fail_prob=0.0 (always succeeds)."""
    return DummyDanceBackend(fail_prob=0.0, seed=42)


@pytest.fixture
def failing_backend():
    """Create a DummyDanceBackend with fail_prob=1.0 (always fails)."""
    return DummyDanceBackend(fail_prob=1.0, seed=42)


@pytest.fixture
def sample_sequence():
    """A simple repaired sequence for testing."""
    return [
        {"skill": "stand_ready", "duration": 1.0, "source": "agent"},
        {"skill": "arm_wave", "duration": 1.5, "source": "agent"},
        {"skill": "final_pose", "duration": 1.0, "source": "agent"},
    ]
```

**CRITICAL:** Note that the SkillRegistry class from Task 02 may have been initialized differently. Check the actual `SkillRegistry` implementation in `humaskill/skills/skill_registry.py` to see how it loads YAML. The constructor/factory pattern may differ from what's shown above. Match the actual API — if `SkillRegistry` constructor takes a YAML path argument, use that. If it has a `load_yaml` class method, use that. If there's a static factory, use that.

### Running Tests

```bash
pytest tests/test_executor.py -q -v
```

---

## Acceptance Criteria

Before declaring this task complete, verify ALL of the following:

1. [ ] `humaskill/backends/base_backend.py` exists with `ExecutionResult` dataclass and `BaseBackend(ABC)` with abstract `execute() -> ExecutionResult`
2. [ ] `humaskill/backends/dummy_backend.py` exists with `DummyDanceBackend(BaseBackend)` supporting `fail_prob` and `seed`
3. [ ] All 6 placeholder backends exist as importable classes inheriting `BaseBackend`, each raising `NotImplementedError`
4. [ ] `humaskill/backends/__init__.py` exports all 9 names (BaseBackend, ExecutionResult, DummyDanceBackend, 6 placeholders)
5. [ ] `humaskill/policies/base_policy.py` exists with `BaseSkillPolicy(ABC)` having abstract `reset()` and `act()`
6. [ ] `humaskill/policies/policy_registry.py` exists with `PolicyRegistry` implementing `register()`, `get()`, `has()`, `all_names()`
7. [ ] `humaskill/policies/policy_adapter.py` exists with `PolicyAdapter` class raising `NotImplementedError`
8. [ ] `humaskill/policies/checkpoint_loader.py` exists with `CheckpointLoader` class raising `NotImplementedError`
9. [ ] `humaskill/policies/__init__.py` exports all 4 names
10. [ ] `humaskill/harness/skill_executor.py` exists with `SkillExecutor` implementing recovery logic
11. [ ] `ExecutionResult.status` uses only `"success"` or `"failed"`
12. [ ] `DummyDanceBackend` is reproducible with the same seed and fail_prob
13. [ ] `SkillExecutor` inserts `recover` skill with `source="recovery_inserted"` on failure
14. [ ] Log entries contain all 11 required fields (index, skill, duration, source, status, start_time, end_time, backend_steps, backend_reward, failure_reason, backend_info)
15. [ ] Summary contains: total_items, total_duration, planned_duration, success_count, failed_count, recover_count, backend_name
16. [ ] Empty sequence execution returns empty logs (no crash)
17. [ ] **`pytest tests/test_backend.py -q` passes with zero failures**
18. [ ] **`pytest tests/test_executor.py -q` passes with zero failures**

---

## General Constraints (Mandatory)

- Follow `INTERFACES.md` strictly — it is the binding contract.
- Only edit the files explicitly allowed in this task (listed under "Allowed Files").
- Use Python 3.10+. Use `str | None` syntax, not `Optional[str]`.
- Use only `PyYAML` and `pytest` as third-party dependencies.
- Write docstrings for core classes and methods.
- Use clear exception messages.
- Handle paths in a way that works on both Windows and Linux.
- **Backend returns `ExecutionResult`, never raw strings.** This is a hard requirement.
- **Executor logs use `status` from `ExecutionResult`, never raw result strings.** This is a hard requirement.
- **Tests must not assume backend returns raw strings.** Tests must use `ExecutionResult.status` to check success/failure.
- Do not modify `INTERFACES.md` or any planning document. If you discover an interface issue, report it in your completion summary but do not change the contract.
