# HumaSkill — Task 03: Composer

## Pre-Flight (READ FIRST)

Before writing any code, read these files in full:

- `PROJECT_PLAN.md` — project goals, system flow, module responsibilities, MVP boundary
- `INTERFACES.md` — binding contract for all agents (especially Section 7: Composer Interface, and Section 2: Raw Sequence Item)
- `TASKS.md` — task breakdown (especially Task 03)
- `ACCEPTANCE_CHECKLIST.md` — acceptance criteria
- `TEST_PLAN.md` — test cases (especially `test_composer.py` section)

---

## Task Goal

Implement the HumaSkill **Composer** module — the component that converts natural language instructions (Chinese text) into raw skill sequences.

Three files to implement, one test file:

1. `BaseComposer` — abstract base class defining the composer interface
2. `RuleBasedDanceComposer` — rule-based implementation that maps Chinese keywords to skill tags, produces deterministic sequences via seed
3. `LLMComposer` — placeholder that inherits BaseComposer and raises NotImplementedError
4. `test_composer.py` — 8 test cases covering all composer behavior

---

## Allowed Files

You may ONLY edit these files:

```
humaskill/composer/__init__.py          (add re-exports)
humaskill/composer/base_composer.py     (create/implement)
humaskill/composer/rule_based_composer.py (create/implement)
humaskill/composer/llm_composer.py      (create/implement)
tests/test_composer.py                  (create/implement)
```

DO NOT edit any other files. DO NOT modify `PROJECT_PLAN.md`, `INTERFACES.md`, `TASKS.md`, `ACCEPTANCE_CHECKLIST.md`, or any file outside this list.

The following modules already exist from prior tasks and should be imported (do not modify them):

- `humaskill.skills.skill_registry` — `SkillRegistry` with `skills_with_tag(tag)` method
- `humaskill.skills.skill_info` — `SkillInfo` dataclass
- `humaskill.utils.errors` — custom exceptions

---

## Interfaces to Follow

### BaseComposer (base_composer.py)

```python
from abc import ABC, abstractmethod


class BaseComposer(ABC):
    @abstractmethod
    def compose(self, text: str, duration: float, seed: int | None = None) -> list[dict]:
        """Convert a language instruction into a raw skill sequence.

        Args:
            text: Natural language instruction (Chinese text)
            duration: Target total duration in seconds
            seed: Optional random seed for reproducibility

        Returns:
            A list of raw sequence items: [{"skill": str, "duration": float}, ...]
        """
        raise NotImplementedError
```

### RuleBasedDanceComposer (rule_based_composer.py)

Constructor:
```python
class RuleBasedDanceComposer(BaseComposer):
    def __init__(self, registry: SkillRegistry):
        """Initialize with a skill registry for skill lookups.

        Args:
            registry: SkillRegistry instance loaded with skills from skills.yaml
        """
```

`compose()` method must follow these rules:

1. **Seed reproducibility**: Use `random.Random(seed)` so the same seed always produces the identical output sequence.

2. **Keyword → tag mapping**: Detect Chinese keywords in the input text and map them to skill tags:

   | Keyword | Tag(s) to use |
   |---------|---------------|
   | `欢快`  | `happy`, `dance` |
   | `优雅`  | `elegant`, `dance` |
   | `力量`  | `power`, `dance` |
   | `机器人` | `robot` (use robot-like skills) |

   If the text contains `欢快` AND `机器人`, combine tags: `happy`, `dance`, `robot`.
   Multiple keywords are additive — all matching tags are used.
   If no keyword is recognized, fall back to `["dance"]` as the default tag.

3. **Always starts with `stand_ready`**: The first item in every sequence MUST be:
   ```python
   {"skill": "stand_ready", "duration": <duration_from_registry>}
   ```
   Use the `duration_range` of `stand_ready` from the registry. Use the midpoint of the range (e.g., if `duration_range: [0.5, 1.5]`, use `1.0`).

4. **Always ends with `final_pose`**: The last item in every sequence MUST be:
   ```python
   {"skill": "final_pose", "duration": <duration_from_registry>}
   ```
   Use the midpoint of its `duration_range` from the registry.

5. **Fills middle with tagged skills**: Between `stand_ready` and `final_pose`, fill the sequence with skills whose tags match the keyword-derived tags. Use `registry.skills_with_tag(tag)` to find candidate skills. Exclude `stand_ready` and `final_pose` from the fill pool.

6. **Respects `duration_range`**: For each skill placed in the sequence, set its duration to the midpoint of the skill's `duration_range` (min+max)/2.

7. **Fills to target duration**: Keep adding skills until the total planned duration is close to the target. The algorithm should:
   - Calculate remaining time after `stand_ready` and `final_pose`
   - Randomly select (using seeded RNG) skills from the matching pool
   - Stop when adding another skill would exceed the target duration by more than one skill's duration
   - The final total duration should be within ±3 seconds of the target (or exactly hit it when possible)

8. **Deterministic with seed**: Given the same seed, text, duration, and registry, the output must be byte-for-byte identical across runs. Use `random.Random(seed)` for all random decisions.

9. **Output format**: Each item is a plain dict with exactly two keys:
   ```python
   {"skill": "<skill_name>", "duration": <float>}
   ```
   - `skill` must be a string matching a registered skill name
   - `duration` must be a positive float

10. **Empty/minimal text**: If the input text is empty or contains no recognized keywords, return a minimal sequence: `[stand_ready, final_pose]` (just the two bookend skills with their default durations).

### LLMComposer (llm_composer.py)

```python
class LLMComposer(BaseComposer):
    """Placeholder for future LLM-based skill composition.

    This class reserves the integration point for an LLM that can
    directly reason about skill sequences from natural language.
    It is intentionally not implemented in the MVP.
    """

    def compose(self, text: str, duration: float, seed: int | None = None) -> list[dict]:
        raise NotImplementedError("LLMComposer is a placeholder for future implementation")
```

---

## Implementation Requirements

### Dependencies

- Python 3.10+
- `PyYAML` (for skill registry YAML loading — already implemented in Task 02)
- `pytest` (for tests)
- Standard library only: `abc`, `random`, `typing`

### Code Quality

- Write docstrings for all public classes and methods.
- Use type hints throughout.
- Use clear, descriptive exception messages.
- Handle edge cases: empty text, zero duration, very short duration, very long duration, unknown skills in registry.
- Platform-agnostic: no hardcoded Windows or Linux paths.

### Imports in `__init__.py`

Update `humaskill/composer/__init__.py` to export:
```python
from humaskill.composer.base_composer import BaseComposer
from humaskill.composer.rule_based_composer import RuleBasedDanceComposer
from humaskill.composer.llm_composer import LLMComposer

__all__ = ["BaseComposer", "RuleBasedDanceComposer", "LLMComposer"]
```

---

## Tests (tests/test_composer.py)

Implement ALL 8 test cases from `TEST_PLAN.md` test_composer section:

| # | Test Name | What It Verifies |
|---|-----------|-----------------|
| 1 | `test_starts_with_stand_ready` | First item in output is `{"skill": "stand_ready", ...}` |
| 2 | `test_ends_with_final_pose` | Last item in output is `{"skill": "final_pose", ...}` |
| 3 | `test_reproducible_with_seed` | Same seed + same inputs → identical outputs (compare dicts exactly) |
| 4 | `test_different_seeds_different_output` | Different seeds may produce different outputs. Use "may" semantics — assert outputs are different for well-separated seeds that produce different random draws. If the pool is small enough that collision is possible, use `pytest.mark.xfail` or document as non-deterministic. Keep the check reasonable: with a diverse skill pool and distinct seeds (e.g., 42 vs 999), the outputs should almost certainly differ. |
| 5 | `test_total_duration_close_to_target` | Sum of all item durations is within ±3.0 seconds of the target duration |
| 6 | `test_style_keyword_affects_skill_pool` | Different keywords produce different skill pools. E.g., "欢快" selects happy+dance skills, "优雅" selects elegant+dance skills, "力量" selects power+dance skills. Verify the middle skills differ between different keyword inputs. |
| 7 | `test_output_is_valid_raw_sequence` | Every item is a dict with `"skill"` (str) and `"duration"` (positive float). No extra keys. No missing keys. All skill names exist in registry. |
| 8 | `test_empty_text_returns_minimal_sequence` | Empty text (or text with no keywords) returns `[stand_ready, final_pose]` — exactly two items |

### Test Fixtures

Create a shared fixture that loads the `SkillRegistry` from `configs/skills.yaml`:

```python
import pytest
from humaskill.skills.skill_registry import SkillRegistry

@pytest.fixture(scope="module")
def registry():
    return SkillRegistry.load_yaml("configs/skills.yaml")
```

### Running Tests

```bash
# Run just composer tests
pytest tests/test_composer.py -q -v

# Run all tests
pytest -q
```

---

## Acceptance Criteria

Before declaring this task complete, verify ALL of the following:

1. [ ] `humaskill/composer/base_composer.py` exists with `BaseComposer(ABC)` having abstract `compose(text, duration, seed=None) -> list[dict]`
2. [ ] `humaskill/composer/rule_based_composer.py` exists with `RuleBasedDanceComposer(BaseComposer)` implementing the 10 rules above
3. [ ] `humaskill/composer/llm_composer.py` exists with `LLMComposer(BaseComposer)` raising `NotImplementedError`
4. [ ] `humaskill/composer/__init__.py` exports all three classes
5. [ ] `tests/test_composer.py` exists with all 8 test cases
6. [ ] `RuleBasedDanceComposer` correctly maps keywords: `欢快` → happy/dance, `优雅` → elegant/dance, `力量` → power/dance, `机器人` → robot
7. [ ] Every sequence starts with `stand_ready` and ends with `final_pose`
8. [ ] Same seed produces identical output (deterministic)
9. [ ] Total duration is within ±3 seconds of target
10. [ ] Empty text returns minimal sequence
11. [ ] All output items match the raw sequence item format: `{"skill": str, "duration": float}`
12. [ ] **`pytest tests/test_composer.py -q` passes with zero failures**

---

## General Constraints (Mandatory)

- Follow `INTERFACES.md` strictly — it is the binding contract.
- Only edit the files explicitly allowed in this task (listed under "Allowed Files").
- Use Python 3.10+.
- Use only `PyYAML` and `pytest` as third-party dependencies.
- Write docstrings for core classes and methods.
- Use clear exception messages.
- Handle paths in a way that works on both Windows and Linux.
- Tests must not assume backend returns raw strings (backend is not involved in this task, but keep this principle in mind for consistency).
- Do not modify `INTERFACES.md` or any planning document. If you discover an interface issue, report it but do not change the contract.
