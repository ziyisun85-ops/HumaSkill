# HumaSkill — Task Breakdown

## Task 01: Project Skeleton and Configs

**Files to create:**
- `README.md` (initial version)
- `requirements.txt`
- `pyproject.toml`
- `.gitignore`
- `configs/skills.yaml`
- `configs/default_config.yaml`
- `examples/demo_dance_request.json`
- `examples/demo_raw_sequence.json`
- `examples/demo_repaired_sequence.json`
- `logs/.gitkeep`
- All `__init__.py` files (empty package files)
- All empty module files in `composer/`, `skills/`, `harness/`, `backends/`, `policies/`, `logging_utils/`, `utils/`

**Goal:** Create complete project skeleton with all empty modules, configuration files, example data files, and directory structure. No logic implemented — just the scaffolding.

---

## Task 02: Utils and Skill Registry

**Files to implement:**
- `humaskill/utils/errors.py` — custom exceptions
- `humaskill/utils/io.py` — YAML and JSON read/write utilities
- `humaskill/utils/math_utils.py` — clamp utility
- `humaskill/utils/printing.py` — formatted printing helpers
- `humaskill/skills/skill_info.py` — `SkillInfo` dataclass
- `humaskill/skills/skill_schema.py` — schema validation for skills
- `humaskill/skills/skill_registry.py` — `SkillRegistry` class
- `scripts/validate_skills.py` — standalone validation script
- `tests/test_skill_registry.py` — tests for SkillRegistry

**Goal:** Implement custom exceptions, YAML/JSON I/O, clamp, SkillInfo, schema validation, SkillRegistry, and the validate_skills script. All tests must pass.

---

## Task 03: Composer

**Files to implement:**
- `humaskill/composer/base_composer.py` — `BaseComposer` ABC
- `humaskill/composer/rule_based_composer.py` — `RuleBasedDanceComposer`
- `humaskill/composer/llm_composer.py` — `LLMComposer` placeholder
- `tests/test_composer.py` — composer tests

**Goal:** Implement `BaseComposer` ABC and `RuleBasedDanceComposer` that converts Chinese text instructions to raw skill sequences. `LLMComposer` is a placeholder. All tests must pass.

---

## Task 04: Transition and Validation

**Files to implement:**
- `humaskill/harness/sequence_validator.py` — validates raw sequence items
- `humaskill/harness/transition_manager.py` — repairs transitions per the 12 rules
- `humaskill/harness/safety_supervisor.py` — monitors safety during execution
- `tests/test_transition_manager.py` — transition repair tests

**Goal:** Implement sequence validation, all 12 transition repair rules, and SafetySupervisor. All tests must pass.

---

## Task 05: Backend, Policy Interface, and Executor

**Files to implement:**
- `humaskill/backends/base_backend.py` — `BaseBackend` ABC
- `humaskill/backends/dummy_backend.py` — `DummyDanceBackend`
- `humaskill/backends/motion_clip_backend.py` — placeholder
- `humaskill/backends/trained_policy_backend.py` — placeholder
- `humaskill/backends/mujoco_gym_backend.py` — placeholder
- `humaskill/backends/isaaclab_backend.py` — placeholder
- `humaskill/backends/textop_backend.py` — placeholder
- `humaskill/backends/groot_backend.py` — placeholder
- `humaskill/policies/base_policy.py` — `BaseSkillPolicy` ABC
- `humaskill/policies/policy_registry.py` — `PolicyRegistry`
- `humaskill/policies/policy_adapter.py` — `PolicyAdapter` placeholder
- `humaskill/policies/checkpoint_loader.py` — `CheckpointLoader` placeholder
- `humaskill/harness/skill_executor.py` — `SkillExecutor` with recovery
- `tests/test_backend.py` — backend tests
- `tests/test_executor.py` — executor tests

**Goal:** Implement `BaseBackend` + `DummyDanceBackend` (with `fail_prob` support), `ExecutionResult`, all placeholder backends/policies, and `SkillExecutor` with recovery logic. All tests must pass.

---

## Task 06: Main, Logging, README Finalization, and Integration Fixes

**Files to implement:**
- `humaskill/main.py` — CLI entry point
- `humaskill/logging_utils/execution_logger.py` — execution log saving
- `humaskill/logging_utils/summary.py` — summary statistics generation
- `scripts/run_demo.py` — demo script
- `README.md` — finalize with full project description
- Integration fixes across all modules

**Goal:** Implement CLI main entry, execution logging, summary statistics, demo script, finalize README. Run demo and full pytest suite. All commands must work:

```bash
python scripts/validate_skills.py
python -m humaskill.main --text "跳一段 12 秒的欢快机器人舞蹈" --duration 12 --seed 42 --fail-prob 0.1 --backend dummy --output logs/demo_log.json
pytest -q
```
