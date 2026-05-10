# HumaSkill — Acceptance Checklist

## Required Commands

All commands must succeed from the project root:

```bash
cd HumaSkill

# 1. Install dependencies
pip install -r requirements.txt

# 2. Validate skill configuration
python scripts/validate_skills.py

# 3. Run demo
python -m humaskill.main \
  --text "跳一段 12 秒的欢快机器人舞蹈" \
  --duration 12 \
  --seed 42 \
  --fail-prob 0.1 \
  --backend dummy \
  --output logs/demo_log.json

# 4. Run all tests
pytest -q
```

---

## Acceptance Criteria

### Project Structure
- [ ] Project structure matches the agreed architecture
- [ ] All `__init__.py` files exist in all packages
- [ ] `logs/.gitkeep` exists

### Configuration
- [ ] `skills.yaml` can be loaded by `validate_skills.py`
- [ ] All skills have: `name`, `tags`, `duration_range`, `start_pose`, `end_pose`, `risk`, `backend`, `policy_id`, `checkpoint`, `action_type`, `obs_adapter`

### Demo Execution
- [ ] `python -m humaskill.main` with demo args runs successfully
- [ ] `logs/demo_log.json` is generated
- [ ] Demo output shows: composer → validator → transition → executor → logs → summary

### Testing
- [ ] `pytest -q` passes all tests with zero failures
- [ ] All 5 test files exist: `test_composer.py`, `test_skill_registry.py`, `test_transition_manager.py`, `test_executor.py`, `test_backend.py`

### README
- [ ] Explains project positioning: skill-level composition harness
- [ ] Explains relationship with TextOp (backend integration)
- [ ] Explains relationship with trained skill policies
- [ ] Documents MuJoCo / Gym backend placeholder
- [ ] Includes usage example with the demo command

### Backend Interfaces
- [ ] `BaseBackend.execute()` returns `ExecutionResult`, not raw string
- [ ] `ExecutionResult` dataclass exists with all required fields
- [ ] `ExecutionResult.status` uses only `"success"` or `"failed"`

### Placeholder Backends
- [ ] `MotionClipBackend` class exists
- [ ] `TrainedPolicyBackend` class exists
- [ ] `MujocoGymBackend` class exists
- [ ] `IsaacLabBackend` class exists
- [ ] `TextOpBackend` class exists
- [ ] `GrootBackend` class exists

### Policy Interfaces
- [ ] `policies/` directory exists
- [ ] `BaseSkillPolicy` ABC exists
- [ ] `PolicyRegistry` class exists
- [ ] `PolicyAdapter` placeholder exists
- [ ] `CheckpointLoader` placeholder exists

### Core Interfaces (INTERFACES.md compliance)
- [ ] `SkillInfo` matches the dataclass definition exactly
- [ ] All custom exceptions exist
- [ ] `SkillRegistry.get()` raises `UnknownSkillError` for unknown skills
- [ ] Repaired sequence items contain `skill`, `duration`, `source`
- [ ] Allowed `source` values: `agent`, `transition_inserted`, `recovery_inserted`, `duration_clamped`
- [ ] `ExecutionResult.status` uses only `success` / `failed`
- [ ] Executor logs use `status`, not raw result strings
- [ ] All 12 transition repair rules are implemented

### Execution Logs
- [ ] Each log item has: `index`, `skill`, `duration`, `source`, `status`, `start_time`, `end_time`
- [ ] Each log item has: `backend_steps`, `backend_reward`, `failure_reason`, `backend_info`
- [ ] Summary statistics are generated

---

## How Hermes Uses This Checklist

After each task completes, Hermes runs: `pytest -q` for the relevant test files. After all tasks complete, Hermes runs the full acceptance checklist above.

Any failed criterion blocks the next task from starting until resolved.
