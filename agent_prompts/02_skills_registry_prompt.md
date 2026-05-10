# Task 02: Utils and Skill Registry

## Task Goal

Implement the HumaSkill utility modules (custom exceptions, YAML/JSON I/O, math clamp, formatted printing), the skills subsystem (`SkillInfo` dataclass, schema validation, `SkillRegistry`), the standalone `validate_skills.py` script, and the full test suite for the skill registry. All implementation must conform exactly to the interfaces defined in `INTERFACES.md`.

---

## Allowed Files

Only these files may be created or modified in this task:

| File | Action |
|---|---|
| `humaskill/utils/errors.py` | Implement — ALL 6 custom exceptions |
| `humaskill/utils/io.py` | Implement — `load_yaml`, `save_json`, `load_json` |
| `humaskill/utils/math_utils.py` | Implement — `clamp(value, min_val, max_val)` |
| `humaskill/utils/printing.py` | Implement — `print_section`, `print_info`, `print_error` |
| `humaskill/skills/skill_info.py` | Implement — `SkillInfo` frozen dataclass |
| `humaskill/skills/skill_schema.py` | Implement — `validate_skill(raw: dict)` |
| `humaskill/skills/skill_registry.py` | Implement — `SkillRegistry` class |
| `scripts/validate_skills.py` | Implement — loads and validates `configs/skills.yaml` |
| `tests/test_skill_registry.py` | Implement — all 8 test cases from TEST_PLAN.md |

No other files may be touched.

---

## Interfaces (Binding Contract)

All interfaces below come from `INTERFACES.md` and MUST be followed exactly.

### 1. SkillInfo Dataclass (INTERFACES.md §1)

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

- Must be a **frozen** dataclass (immutable after creation).
- Every field must match the name, type, and default exactly.

### 2. SkillRegistry Interface (INTERFACES.md §9)

```python
get(name: str) -> SkillInfo
has(name: str) -> bool
all_names() -> list[str]
skills_with_tag(tag: str) -> list[SkillInfo]
```

- `get()` MUST raise `UnknownSkillError` when the skill name is not found.
- Registry loads from a YAML file (e.g., `configs/skills.yaml`).

### 3. Required Exceptions (INTERFACES.md §10)

```python
class HumaSkillError(Exception):
    """Base exception for HumaSkill."""
    pass

class UnknownSkillError(HumaSkillError):
    """Skill not found in registry."""
    pass

class InvalidSkillConfigError(HumaSkillError):
    """Skill configuration validation failed."""
    pass

class InvalidSequenceError(HumaSkillError):
    """Sequence validation failed."""
    pass

class BackendExecutionError(HumaSkillError):
    """Backend execution failed."""
    pass

class PolicyLoadError(HumaSkillError):
    """Policy checkpoint loading failed."""
    pass
```

All six MUST be implemented exactly as shown.

---

## Detailed Requirements

### `humaskill/utils/errors.py`

Implement all 6 exception classes from INTERFACES.md §10:
- `HumaSkillError` — base exception
- `UnknownSkillError` — skill not found
- `InvalidSkillConfigError` — bad skill config
- `InvalidSequenceError` — bad sequence
- `BackendExecutionError` — backend failure
- `PolicyLoadError` — checkpoint load failure

Each must inherit correctly. Use the exact class names and docstrings shown.

### `humaskill/utils/io.py`

Three functions:

- `load_yaml(path: str) -> dict` — reads a YAML file, returns parsed dict
- `save_json(path: str, data) -> None` — writes data to JSON file
- `load_json(path: str) -> dict` — reads a JSON file, returns parsed dict

Use `PyYAML` for YAML and the standard `json` module for JSON. Handle file not found and parse errors with clear exception messages (use `HumaSkillError` or standard Python exceptions appropriate to the situation).

### `humaskill/utils/math_utils.py`

One function:

- `clamp(value: float, min_val: float, max_val: float) -> float` — returns `value` clamped to the inclusive range `[min_val, max_val]`

If `min_val > max_val`, raise a `ValueError`.

### `humaskill/utils/printing.py`

Three functions:

- `print_section(title: str) -> None` — prints a formatted section header (e.g., with separator lines)
- `print_info(msg: str) -> None` — prints an informational message (e.g., prefixed with `[INFO]`)
- `print_error(msg: str) -> None` — prints an error message (e.g., prefixed with `[ERROR]`)

Choose clear, visually distinguishable formatting. The format does not need to match a spec — just be clean and readable on a terminal.

### `humaskill/skills/skill_info.py`

Implement the `SkillInfo` frozen dataclass exactly as shown in INTERFACES.md §1. All fields, types, defaults, and `frozen=True`.

### `humaskill/skills/skill_schema.py`

Function: `validate_skill(raw: dict) -> None`

Validates that a raw skill dict (loaded from YAML) has the required fields and correct types. Raise `InvalidSkillConfigError` if any of these checks fail:

- Required fields: `name`, `tags`, `duration_range`, `start_pose`, `end_pose`, `risk`
- `name` must be a non-empty `str`
- `tags` must be a `list[str]` (non-empty)
- `duration_range` must be a list/tuple of exactly 2 numbers with `min < max`
- `start_pose` must be a non-empty `str`
- `end_pose` must be a non-empty `str`
- `risk` must be one of: `"low"`, `"medium"`, `"high"`

The error message for each failure should name the skill and the reason (for clear debugging in the validation script).

### `humaskill/skills/skill_registry.py`

Class `SkillRegistry`:

Constructor: `__init__(self, skills_yaml_path: str)`
- Loads the YAML file at `skills_yaml_path`.
- Validates each raw skill dict using `validate_skill()` from `skill_schema.py`.
- Stores each valid skill as a `SkillInfo` instance in an internal dict keyed by `name`.

Methods:
- `get(name: str) -> SkillInfo` — returns the `SkillInfo` for `name`. Raises `UnknownSkillError` if not found.
- `has(name: str) -> bool` — returns `True` if `name` is registered.
- `all_names() -> list[str]` — returns a list of all registered skill names.
- `skills_with_tag(tag: str) -> list[SkillInfo]` — returns all `SkillInfo` instances that have the given tag in their `tags` list.

### `scripts/validate_skills.py`

Standalone script that:
1. Loads `configs/skills.yaml` (path relative to project root, or discover it).
2. Validates every skill in the YAML using `validate_skill()`.
3. Reports results: prints which skills pass, which fail (with reason).
4. Exits with code 0 if all skills valid, non-zero if any fail.

The script must be runnable from the project root:
```bash
python scripts/validate_skills.py
```

### `tests/test_skill_registry.py`

Must cover all 8 test cases from TEST_PLAN.md:

| # | Test | Description |
|---|---|---|
| 1 | `test_load_skills_yaml` | `skills.yaml` loads successfully, returns non-empty registry |
| 2 | `test_stand_ready_exists` | `stand_ready` is present in the registry |
| 3 | `test_recover_exists` | `recover` is present in the registry |
| 4 | `test_all_names_returns_list` | `all_names()` returns a non-empty list of strings |
| 5 | `test_unknown_skill_raises_error` | Querying a non-existent skill raises `UnknownSkillError` |
| 6 | `test_extended_fields_loaded` | `backend`, `policy_id`, `checkpoint`, `action_type`, `obs_adapter` fields are loaded from YAML |
| 7 | `test_skills_with_tag` | `skills_with_tag("dance")` returns only skills tagged `"dance"` |
| 8 | `test_skill_info_dataclass` | `SkillInfo` is a frozen dataclass with all required fields |

Tests must use `pytest` and import from the `humaskill` package. Use the `configs/skills.yaml` file in the project root as the test data source.

---

## Acceptance Criteria

- [ ] All 6 custom exceptions exist in `humaskill/utils/errors.py`
- [ ] `load_yaml`, `save_json`, `load_json` work correctly
- [ ] `clamp` function clamps values and raises `ValueError` for invalid bounds
- [ ] `print_section`, `print_info`, `print_error` produce readable terminal output
- [ ] `SkillInfo` matches INTERFACES.md §1 exactly (frozen dataclass with all fields)
- [ ] `validate_skill()` catches all invalid config cases and raises `InvalidSkillConfigError`
- [ ] `SkillRegistry.get()` raises `UnknownSkillError` for unknown skills
- [ ] `SkillRegistry` implements `get()`, `has()`, `all_names()`, `skills_with_tag()`
- [ ] `scripts/validate_skills.py` runs successfully and reports results
- [ ] All 8 tests in `tests/test_skill_registry.py` pass with `pytest -q tests/test_skill_registry.py`

---

## Restrictions

1. Python 3.10+ only. Use `str | None` syntax, not `Optional[str]`.
2. Dependencies: `PyYAML` and `pytest` only. No other third-party packages.
3. `SkillInfo` MUST be a frozen dataclass — no custom `__init__`, no mutable defaults.
4. `validate_skill()` MUST raise `InvalidSkillConfigError` (not generic exceptions) for config errors.
5. `SkillRegistry.get()` MUST raise `UnknownSkillError` (not `KeyError` or generic exceptions).
6. All function signatures must match the specifications above exactly.
7. Do NOT modify any file outside the "Allowed Files" list above.
8. Use docstrings for all public functions and classes.
9. Use clear exception messages — include the skill name and reason in every error.

---

## Must-Read Docs Before Starting

The following files in the project root define the binding contract for this task. Read them completely before writing any code:

1. **`INTERFACES.md`** — §§1, 9, 10 define the exact interfaces for `SkillInfo`, `SkillRegistry`, and all 6 custom exceptions. These are non-negotiable.

2. **`TEST_PLAN.md`** — `test_skill_registry` section defines all 8 required test cases. Every test must be implemented.

3. **`ACCEPTANCE_CHECKLIST.md`** — Core Interfaces section lists the items that must pass for this task.

4. **`TASKS.md`** — Task 02 section lists the exact files to create/modify.

5. **`PROJECT_PLAN.md`** — Module Responsibilities section explains the purpose of the `skills` and `utils` modules.

6. **`configs/skills.yaml`** — The actual skill definitions to load and validate. Know its structure before implementing the registry.

---

## Strict Interface Adherence

This is the most important rule of this task:

> Every interface in `INTERFACES.md` is a binding contract. Do not deviate — not in class names, not in field names, not in method signatures, not in exception types, not in return types.

If you believe an interface is wrong, incomplete, or ambiguous, do NOT change it. Instead, note the issue clearly in your completion summary so the project maintainer can update `INTERFACES.md` and re-issue the task.

---

## Verification

After implementation, run from the project root:

```bash
# Validate all skills
python scripts/validate_skills.py

# Run the skill registry tests
pytest tests/test_skill_registry.py -v
```

Both must succeed with zero errors.
