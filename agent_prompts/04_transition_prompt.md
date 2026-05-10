# HumaSkill — Task 04: Transition and Validation

## Pre-Flight (READ FIRST)

Before writing any code, read these files in full:

- `PROJECT_PLAN.md` — project goals, system flow (especially the Validator → TransitionManager pipeline), module responsibilities
- `INTERFACES.md` — binding contract for all agents. **Especially critical: Section 11 (all 12 transition repair rules), Section 2 (Raw Sequence Item), Section 3 (Repaired Sequence Item), Section 4 (ExecutionResult), Section 10 (Required Exceptions)**
- `TASKS.md` — task breakdown (especially Task 04)
- `ACCEPTANCE_CHECKLIST.md` — acceptance criteria
- `TEST_PLAN.md` — test cases (especially `test_transition_manager.py` section with all 9 tests)

---

## Task Goal

Implement the HumaSkill **Sequence Validator**, **Transition Manager** (all 12 repair rules from INTERFACES.md §11), and **Safety Supervisor**. These three components sit between the composer and executor in the system flow, ensuring raw skill sequences are valid and repaired for safe, executable transitions.

Four files to implement:

1. `SequenceValidator` — validates raw sequence items from composer output, rejects invalid items
2. `TransitionManager` — repairs transitions per the 12 rules: pose matching, risk-based inserts, duration clamping
3. `SafetySupervisor` — monitoring placeholder for execution safety (lightweight in MVP)
4. `test_transition_manager.py` — 9 test cases covering all transition repair rules

---

## Allowed Files

You may ONLY edit these files:

```
humaskill/harness/__init__.py              (add re-exports)
humaskill/harness/sequence_validator.py    (create/implement)
humaskill/harness/transition_manager.py    (create/implement)
humaskill/harness/safety_supervisor.py     (create/implement)
tests/test_transition_manager.py           (create/implement)
```

DO NOT edit any other files. DO NOT modify `PROJECT_PLAN.md`, `INTERFACES.md`, `TASKS.md`, `ACCEPTANCE_CHECKLIST.md`, `TEST_PLAN.md`, or any file outside this list.

The following modules already exist from prior tasks and should be imported (do not modify them):

- `humaskill.skills.skill_registry` — `SkillRegistry` with `get()`, `has()`, `all_names()`, `skills_with_tag()` methods
- `humaskill.skills.skill_info` — `SkillInfo` frozen dataclass (name, tags, duration_range, start_pose, end_pose, risk, ...)
- `humaskill.utils.errors` — all 6 custom exceptions: `HumaSkillError`, `UnknownSkillError`, `InvalidSequenceError`, etc.

---

## Interfaces to Follow

### SequenceValidator

```python
class SequenceValidator:
    """Validates raw sequence items from composer output."""

    def __init__(self, registry: SkillRegistry):
        """Initialize with a skill registry for skill existence checks."""

    def validate(self, raw_sequence: list[dict]) -> None:
        """Validate every item in a raw sequence.

        Each item must:
        - Be a dict with keys 'skill' and 'duration'
        - 'skill' must be a non-empty string existing in the registry
        - 'duration' must be a positive number (int or float, > 0)

        Raises InvalidSequenceError if any item is invalid.
        The error message must include the specific item or index and the reason.
        """
```

Validation rules:
1. Every item must be a `dict` with keys `"skill"` and `"duration"` (exactly those two keys from raw composer output).
2. `"skill"` must be a non-empty `str` that exists in the registry (use `registry.has()`).
3. `"duration"` must be a positive number (`int` or `float`, > 0).
4. The sequence itself must not be empty.
5. On any failure, raise `InvalidSequenceError` with a message that identifies the offending item (by index or skill name) and the reason.
6. On success, return `None` (no return value).

### TransitionManager (CRITICAL — All 12 Rules)

```python
class TransitionManager:
    """Repairs skill sequences to ensure safe, executable transitions.

    Applies 12 transition repair rules from INTERFACES.md §11 in order.
    """

    def __init__(self, registry: SkillRegistry):
        """Initialize with a skill registry for skill metadata lookups."""

    def repair(self, sequence: list[dict]) -> list[dict]:
        """Apply all transition repair rules to a sequence.

        Args:
            sequence: Validated raw sequence items [{"skill": str, "duration": float}, ...]

        Returns:
            Repaired sequence items [{"skill": str, "duration": float, "source": str}, ...]
            Every output item has: skill, duration, source.
        """
```

#### The 12 Transition Repair Rules (INTERFACES.md §11)

Apply these rules in order on the sequence:

| Rule | Description | Details |
|------|-------------|---------|
| 1 | Mark composer items | All items that come from the original sequence get `source = "agent"` |
| 2 | Clamp out-of-range durations | If an item's `duration` exceeds the skill's `duration_range` (min, max) from the registry, clamp it to the nearest valid value |
| 3 | Mark clamped items | If duration was clamped by Rule 2, set `source = "duration_clamped"` |
| 4 | Pose match — keep as-is | If the current humanoid pose matches the next skill's `start_pose`, keep the item unchanged |
| 5 | "any" pose — allow | If the next skill's `start_pose` is `"any"`, no pose-based insert is triggered |
| 6 | `low_pose` → `standing` | If current pose is `"low_pose"` and the next skill requires `"standing"`, insert `stand_up` before it |
| 7 | Pose mismatch — general | If current pose and the next skill's `start_pose` don't match (and Rule 5/6 don't apply), insert `stand_stable` before it |
| 8 | High risk — before | Before a skill with `risk = "high"`, insert `stand_stable` |
| 9 | High risk — after | After a skill with `risk = "high"`, insert `stand_stable` |
| 10 | Medium risk — after | After a skill with `risk = "medium"`, insert `stand_stable` |
| 11 | Inserted source | Every item inserted by Rules 6–10 MUST have `source = "transition_inserted"` |
| 12 | All items have 3 keys | Every item in the output MUST contain: `skill`, `duration`, `source` |

#### Default Insert Durations (INTERFACES.md §11)

| Insert Skill | Duration |
|-------------|----------|
| `stand_stable` | 0.8 |
| `stand_up` | 1.2 |
| `recover` | 1.5 |

Use `recover` only in the executor (Task 05) — TransitionManager does NOT insert `recover`. Recovery is handled by `SkillExecutor` when the backend returns `failed`.

#### Pose Tracking

The `repair()` method must track the current humanoid pose as it processes the sequence:

- Start pose: `"standing"` (humanoid begins standing)
- After each skill executes, the current pose becomes that skill's `end_pose`
- This tracked pose is used for Rules 4–7 to decide whether insertions are needed

#### Rule Application Order

Rules 1–3 (marking and clamping) apply to all items BEFORE the pose-tracking loop. Rules 4–12 apply during the iterative processing pass, where the TransitionManager walks through the sequence left-to-right and builds the repaired output list. When an insertion happens (Rules 6–10), the inserted skill's `end_pose` updates the tracked pose before continuing.

#### Edge Cases

- **Empty sequence**: Return an empty list (no crash)
- **Single-item sequence**: Apply Rules 1–5 without pose-matching (no "next" skill); still check risk-based inserts (Rules 8–10)
- **Consecutive inserts**: If multiple rules trigger for the same position (e.g., `squat` is high risk AND ends in `low_pose`), apply all applicable rules in order. Example for `squat` followed by `arm_wave`: insert `stand_stable` before `squat` (Rule 8), after `squat` insert `stand_stable` (Rule 9), then since pose is now `low_pose` and `arm_wave` requires `standing`, insert `stand_up` (Rule 6), plus `stand_stable` after (Rule 10 does NOT apply to `squat`'s risk inserts — only to the original `squat`).
- **Unknown skill**: If `registry.has(name)` returns `False` for any skill in the input sequence, raise `UnknownSkillError` (or let `registry.get()` raise it naturally).

#### Allowed `source` Values (INTERFACES.md §3)

| Value | Meaning |
|-------|---------|
| `"agent"` | Item came from composer output |
| `"transition_inserted"` | Item inserted by TransitionManager for pose bridging or risk safety |
| `"recovery_inserted"` | Item inserted by execution recovery logic (NOT used by TransitionManager — reserved for SkillExecutor) |
| `"duration_clamped"` | Original item had out-of-range duration, clamped to valid range |

### SafetySupervisor

```python
class SafetySupervisor:
    """Monitors safety during skill execution.

    In the MVP, this is a lightweight monitoring class that tracks
    the execution state and can flag safety concerns. Full safety
    checks (joint limits, velocity limits, collision detection)
    are reserved for future backends (MuJoCo, Isaac Lab).
    """

    def __init__(self):
        """Initialize the safety supervisor."""

    def check_pre_execution(self, skill_name: str) -> bool:
        """Check safety before executing a skill.

        Returns True if safe to proceed, False if a safety stop is needed.
        In MVP, always returns True.
        """

    def check_post_execution(self, skill_name: str, result) -> bool:
        """Check safety after executing a skill.

        result is an ExecutionResult from the backend.
        Returns True if safe to continue, False if recovery is needed.
        In MVP, returns True unless the result itself indicates failure.
        """

    def reset(self) -> None:
        """Reset safety state for a new execution run."""
```

The SafetySupervisor is intentionally minimal in MVP. It provides the interface points for future safety logic. The key design: it receives `ExecutionResult` objects (not raw strings) from the backend.

---

## Implementation Requirements

### Dependencies

- Python 3.10+
- `PyYAML` (for skill registry YAML loading — already implemented in Task 02)
- `pytest` (for tests)
- Standard library only: `copy`, `typing`

### Code Quality

- Write docstrings for all public classes and methods.
- Use type hints throughout (`list[dict]`, `str | None`, etc.).
- Use clear, descriptive exception messages — include the skill name and reason in every error.
- Handle edge cases: empty sequence, single-item sequence, all-known skills, unknown skills, extreme durations.
- Platform-agnostic: no hardcoded Windows or Linux paths.
- `TransitionManager.repair()` should NOT modify the input sequence in-place — return a new list.

### Imports in `__init__.py`

Update `humaskill/harness/__init__.py` to export:

```python
from humaskill.harness.sequence_validator import SequenceValidator
from humaskill.harness.transition_manager import TransitionManager
from humaskill.harness.safety_supervisor import SafetySupervisor

__all__ = ["SequenceValidator", "TransitionManager", "SafetySupervisor"]
```

---

## Tests (tests/test_transition_manager.py)

Implement ALL 9 test cases from `TEST_PLAN.md` test_transition_manager section:

| # | Test Name | What It Verifies |
|---|-----------|-----------------|
| 1 | `test_high_risk_inserts_stand_stable_before` | High risk skill (`squat`) has `stand_stable` inserted before it with `source = "transition_inserted"` |
| 2 | `test_high_risk_inserts_stand_stable_after` | High risk skill (`squat`) has `stand_stable` inserted after it with `source = "transition_inserted"` |
| 3 | `test_medium_risk_inserts_stand_stable_after` | Medium risk skill (`turn_left` or `turn_right`) has `stand_stable` inserted after it |
| 4 | `test_squat_to_standing_inserts_stand_up` | Sequence: `squat` (end_pose=`low_pose`) → standing skill (start_pose=`standing`) inserts `stand_up` between them |
| 5 | `test_duration_clamped` | Out-of-range duration (e.g., 10.0 for a skill with `duration_range: [0.5, 3.0]`) is clamped to max; `source` becomes `"duration_clamped"` |
| 6 | `test_unknown_skill_raises_error` | Referencing a skill not in the registry raises `UnknownSkillError` (via `registry.get()`) or `InvalidSequenceError` |
| 7 | `test_repaired_items_have_required_fields` | Every item in the repaired output is a dict with exactly (at minimum) the keys: `"skill"`, `"duration"`, `"source"` — no missing keys, all values are correct types |
| 8 | `test_any_pose_allows_any_start` | Skills with `start_pose: "any"` (like `stand_ready`, `recover`, `stand_stable`) don't trigger pose-based inserts (Rule 5) |
| 9 | `test_low_risk_no_inserts` | Low risk skills (like `arm_wave`, `body_sway`) don't trigger risk-based inserts (Rules 8–10); only pose-matching rules apply |

### Test Fixtures

Create a shared fixture that loads the `SkillRegistry` from `configs/skills.yaml`:

```python
import pytest
from humaskill.skills.skill_registry import SkillRegistry

@pytest.fixture(scope="module")
def registry():
    """Load the skill registry once for all tests in this module."""
    return SkillRegistry("configs/skills.yaml")
```

### Additional Fixture

```python
@pytest.fixture
def transition_manager(registry):
    """Create a TransitionManager with the loaded registry."""
    from humaskill.harness.transition_manager import TransitionManager
    return TransitionManager(registry)
```

### Test Construction Guidelines

- Build input sequences as lists of dicts with `"skill"` and `"duration"` (raw sequence format).
- Run them through `TransitionManager.repair()`.
- Assert on the output: check inserted items, `source` fields, `duration` clamping, item count.
- For `test_unknown_skill_raises_error`, use `pytest.raises(UnknownSkillError)` (or `InvalidSequenceError` if the validator catches it first).
- Each test should be independent and not rely on sequence from other tests.

### Running Tests

```bash
# Run just transition manager tests
pytest tests/test_transition_manager.py -q -v

# Run all tests (after all tasks complete)
pytest -q
```

---

## Acceptance Criteria

Before declaring this task complete, verify ALL of the following:

1. [ ] `humaskill/harness/sequence_validator.py` exists with `SequenceValidator` class
2. [ ] `SequenceValidator.validate()` rejects items missing `"skill"` or `"duration"`, invalid skill names, non-positive durations, and empty sequences — all with clear `InvalidSequenceError` messages
3. [ ] `humaskill/harness/transition_manager.py` exists with `TransitionManager` class
4. [ ] ALL 12 transition repair rules from INTERFACES.md §11 are implemented and applied in order
5. [ ] `TransitionManager.repair()` correctly tracks pose through the sequence
6. [ ] Inserted items use the correct default durations: `stand_stable` = 0.8, `stand_up` = 1.2
7. [ ] Inserted items have `source = "transition_inserted"`
8. [ ] Clamped items have `source = "duration_clamped"`
9. [ ] Original items have `source = "agent"`
10. [ ] Every output item contains: `skill`, `duration`, `source` (Rule 12)
11. [ ] `humaskill/harness/safety_supervisor.py` exists with `SafetySupervisor` class
12. [ ] `SafetySupervisor` has `check_pre_execution()`, `check_post_execution()`, `reset()` methods
13. [ ] `SafetySupervisor` works with `ExecutionResult` objects, not raw strings
14. [ ] `humaskill/harness/__init__.py` exports `SequenceValidator`, `TransitionManager`, `SafetySupervisor`
15. [ ] `tests/test_transition_manager.py` exists with all 9 test cases
16. [ ] **`pytest tests/test_transition_manager.py -q` passes with zero failures**
17. [ ] Tests do not assume backend returns raw strings (tests validate `ExecutionResult` structure where backend results are involved)

---

## General Constraints (Mandatory)

- **Follow INTERFACES.md strictly.** It is the binding contract. Every rule, field name, source value, and duration in §11 must be followed exactly.
- **Only edit the files explicitly allowed** in this task (listed under "Allowed Files").
- **Use Python 3.10+.** Use `str | None` syntax, not `Optional[str]`. Use `list[dict]`, not `List[dict]`.
- **Use only `PyYAML` and `pytest`** as third-party dependencies. No other packages (no numpy, no requests, no click).
- **Backend returns `ExecutionResult`.** This is a binding design constraint. The SafetySupervisor's `check_post_execution()` receives an `ExecutionResult`, never a raw string. Tests that involve backend results must use `ExecutionResult` objects.
- **Executor logs use `status`.** Log items use `"success"` / `"failed"` strings — this matters for `ExecutionResult.status` that flows through to logs (implemented in Task 05).
- **Tests must not assume backend returns raw strings.** Any test that touches backend results must validate on `ExecutionResult` structure, not string parsing.
- **Write docstrings** for all public classes and methods.
- **Use clear exception messages.** Include skill names and reasons in every error.
- **Handle paths** in a way that works on both Windows and Linux.
- **Do not modify `INTERFACES.md`** or any planning document. If you discover an interface issue, report it in your completion summary but do not change the contract.
- **`TransitionManager` does NOT insert `recover`.** Recovery insertion is the executor's responsibility (Task 05). TransitionManager only inserts `stand_stable` and `stand_up`.
- **Do not modify input in-place.** `repair()` returns a new list; it does not mutate the input sequence.

---

## Strict Interface Adherence

This is the most important rule of this task:

> Every interface in `INTERFACES.md` is a binding contract. Do not deviate — not in class names, not in method signatures, not in rule order, not in field names, not in source values, not in exception types, not in return types.

The 12 transition repair rules in §11 are the heart of this task. Every rule must be implemented exactly as specified and applied in the given order. If you believe a rule is wrong, incomplete, or ambiguous, do NOT change it. Instead, note the issue clearly in your completion summary so the project maintainer can update `INTERFACES.md` and re-issue the task.

---

## Verification

After implementation, run from the project root:

```bash
# Run just the transition manager tests
pytest tests/test_transition_manager.py -v

# Run all existing tests (if prior task tests exist)
pytest -q
```

Both must succeed with zero errors.
