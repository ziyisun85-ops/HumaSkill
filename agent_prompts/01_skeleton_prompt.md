# Task 01: Project Skeleton and Configs

## Before You Begin

You MUST read these files first for full context:

- `PROJECT_PLAN.md` — project goal, MVP scope, module responsibilities, project structure
- `INTERFACES.md` — binding contract: all dataclass definitions, interfaces, transition repair rules, constraints
- `TASKS.md` — full task breakdown and Task 01 details
- `ACCEPTANCE_CHECKLIST.md` — acceptance criteria for the full project
- `TEST_PLAN.md` — all required test cases (for awareness, not implementation in this task)

## Task Goal

Create the complete project skeleton with all empty module files, configuration files, example data files, and directory structure. **No logic is implemented in this task** — this is pure scaffolding. Every `.py` file is created empty (or with minimal placeholder docstrings for module files, empty for `__init__.py` files). The configuration and example JSON files are fully populated as specified.

## Allowed Files to Edit

**ONLY the files listed below may be created or edited in this task.** Do not touch any other files.

### Root-Level Files
- `README.md`
- `requirements.txt`
- `pyproject.toml`
- `.gitignore`

### Configuration Files
- `configs/skills.yaml`
- `configs/default_config.yaml`

### Example Data Files
- `examples/demo_dance_request.json`
- `examples/demo_raw_sequence.json`
- `examples/demo_repaired_sequence.json`

### Log Directory Placeholder
- `logs/.gitkeep`

### Package `__init__.py` Files (all empty)
- `humaskill/__init__.py`
- `humaskill/composer/__init__.py`
- `humaskill/skills/__init__.py`
- `humaskill/harness/__init__.py`
- `humaskill/backends/__init__.py`
- `humaskill/policies/__init__.py`
- `humaskill/logging_utils/__init__.py`
- `humaskill/utils/__init__.py`
- `tests/__init__.py`

### Empty Module Files (create as empty `.py` files with no content)
- `humaskill/main.py`
- `humaskill/composer/base_composer.py`
- `humaskill/composer/rule_based_composer.py`
- `humaskill/composer/llm_composer.py`
- `humaskill/skills/skill_info.py`
- `humaskill/skills/skill_registry.py`
- `humaskill/skills/skill_schema.py`
- `humaskill/harness/sequence_validator.py`
- `humaskill/harness/transition_manager.py`
- `humaskill/harness/skill_executor.py`
- `humaskill/harness/safety_supervisor.py`
- `humaskill/backends/base_backend.py`
- `humaskill/backends/dummy_backend.py`
- `humaskill/backends/motion_clip_backend.py`
- `humaskill/backends/trained_policy_backend.py`
- `humaskill/backends/mujoco_gym_backend.py`
- `humaskill/backends/isaaclab_backend.py`
- `humaskill/backends/textop_backend.py`
- `humaskill/backends/groot_backend.py`
- `humaskill/policies/base_policy.py`
- `humaskill/policies/policy_registry.py`
- `humaskill/policies/policy_adapter.py`
- `humaskill/policies/checkpoint_loader.py`
- `humaskill/logging_utils/execution_logger.py`
- `humaskill/logging_utils/summary.py`
- `humaskill/utils/io.py`
- `humaskill/utils/math_utils.py`
- `humaskill/utils/printing.py`
- `humaskill/utils/errors.py`
- `tests/test_composer.py`
- `tests/test_skill_registry.py`
- `tests/test_transition_manager.py`
- `tests/test_executor.py`
- `tests/test_backend.py`

**Script files (`scripts/validate_skills.py`, `scripts/run_demo.py`) are NOT created in this task.** They are implemented in later tasks (Task 02 and Task 06 respectively).

## Interfaces to Follow

You MUST follow `INTERFACES.md` strictly. Key references for this task:

- **SkillInfo dataclass** (Section 1): All fields must be present in every skill entry in `skills.yaml`
- **Raw Sequence Item** (Section 2): `{"skill": str, "duration": float}` — used in `demo_raw_sequence.json`
- **Repaired Sequence Item** (Section 3): `{"skill": str, "duration": float, "source": str}` — used in `demo_repaired_sequence.json`
- **Allowed `source` values** (Section 3): `"agent"`, `"transition_inserted"`, `"recovery_inserted"`, `"duration_clamped"`
- **Transition Repair Rules** (Section 11): These dictate skill pose compatibilities and insert behavior — ensure skills.yaml is consistent with these rules
- **General Constraints** (Section 13): Python 3.10+, PyYAML + pytest only, Backend returns `ExecutionResult`, Executor logs use `status`

## Implementation Requirements

### 1. README.md

Initial version. Must include:
- Project name: **HumaSkill**
- One-line description: "Skill-level composition and execution harness for language-guided humanoid motion composition"
- Link or reference to the project structure (can say "See PROJECT_PLAN.md for full project structure")
- Keep it brief — placeholder README that will be finalized in Task 06

### 2. requirements.txt

**Exactly** two lines:
```
pyyaml
pytest
```
No version pins. No other packages. No blank lines at start/end (one entry per line).

### 3. pyproject.toml

Minimal valid `pyproject.toml`:
- `requires-python = ">=3.10"`
- Package name: `humaskill`
- Version: `0.1.0`
- Dependencies: `pyyaml` only (pytest is a test dependency, not a runtime dependency)
- Use `setuptools` as the build backend
- No `[tool.pytest]` section needed at this stage

### 4. .gitignore

Must ignore at minimum:
- `__pycache__/`
- `*.pyc`
- `.pytest_cache/`
- `*.egg-info/`
- `dist/`
- `logs/*.json`

Add standard Python gitignore entries (`.venv/`, `.env`, `*.pyo`, etc.) as appropriate.

### 5. configs/skills.yaml

**CRITICAL: Must contain EXACTLY 12 skills with ALL fields from the SkillInfo dataclass (INTERFACES.md Section 1).** Every skill must have: `name`, `tags`, `duration_range`, `start_pose`, `end_pose`, `risk`, `description`, `backend`, `policy_id`, `checkpoint`, `action_type`, `obs_adapter`.

Even for the dummy backend, include `backend: dummy` and set the future fields (`policy_id`, `checkpoint`, `action_type`, `obs_adapter`) to `null`.

#### Required Skills (12 total):

| # | name | tags | duration_range | start_pose | end_pose | risk | notes |
|---|------|------|----------------|------------|----------|------|-------|
| 1 | `stand_ready` | `["basic"]` | `[0.5, 2.0]` | `any` | `standing` | `low` | Initial pose, composer always emits this first |
| 2 | `stand_stable` | `["basic"]` | `[0.3, 1.5]` | `any` | `standing` | `low` | Stabilization insert; transition default duration 0.8 |
| 3 | `stand_up` | `["basic"]` | `[0.8, 2.0]` | `low_pose` | `standing` | `medium` | Low→standing transition; transition default duration 1.2 |
| 4 | `final_pose` | `["basic"]` | `[0.5, 3.0]` | `standing` | `standing` | `low` | Ending pose, composer always emits this last |
| 5 | `recover` | `["basic"]` | `[1.0, 3.0]` | `any` | `standing` | `medium` | Recovery after failed execution; transition default duration 1.5 |
| 6 | `arm_wave` | `["happy", "dance"]` | `[0.5, 3.0]` | `standing` | `standing` | `low` | Cheerful arm waving dance move |
| 7 | `body_sway` | `["elegant", "dance"]` | `[0.5, 3.0]` | `standing` | `standing` | `low` | Graceful body swaying |
| 8 | `step_forward` | `["power", "dance"]` | `[0.5, 2.0]` | `standing` | `standing` | `low` | Step forward with power |
| 9 | `step_backward` | `["power", "dance"]` | `[0.5, 2.0]` | `standing` | `standing` | `low` | Step backward with power |
| 10 | `turn_left` | `["elegant", "dance"]` | `[0.5, 2.0]` | `standing` | `standing` | `medium` | Turn left — medium risk triggers `stand_stable` insert after |
| 11 | `turn_right` | `["elegant", "dance"]` | `[0.5, 2.0]` | `standing` | `standing` | `medium` | Turn right — medium risk triggers `stand_stable` insert after |
| 12 | `squat` | `["power", "dance"]` | `[0.8, 3.0]` | `standing` | `low_pose` | `high` | Squat ends in low_pose — triggers `stand_up` insert + `stand_stable` before/after (high risk) |

#### Design Rationale (ensuring transition repair rules are exercisable):

- **`squat`** (high risk, end_pose = `low_pose`): Exercises Rules 6, 8, 9 — before squat inserts `stand_stable`, after squat inserts `stand_stable`, then next standing skill triggers `stand_up`
- **`turn_left` / `turn_right`** (medium risk): Exercises Rule 10 — after each, `stand_stable` is inserted
- **`stand_up`** (start_pose = `low_pose`): Exercises Rule 6 — only used when transitioning from low_pose to standing
- **`stand_ready` / `recover`** (start_pose = `any`): Exercises Rule 5 — no pose-based inserts needed
- **`stand_stable`** (start_pose = `any`): Exercises Rule 5 — universal stabilizer

#### YAML Format:

Each skill entry:
```yaml
- name: stand_ready
  tags: [basic]
  duration_range: [0.5, 2.0]
  start_pose: any
  end_pose: standing
  risk: low
  description: "Initial ready stance — standing upright, arms at sides"
  backend: dummy
  policy_id: null
  checkpoint: null
  action_type: null
  obs_adapter: null
```

Write meaningful `description` strings for every skill in English (describing what the humanoid does).

### 6. configs/default_config.yaml

```yaml
fail_prob: 0.1
backend: dummy
default_duration: 12
seed: 42
```

### 7. examples/demo_dance_request.json

Example user request input:
```json
{
  "text": "跳一段 12 秒的欢快机器人舞蹈",
  "duration": 12.0,
  "seed": 42,
  "fail_prob": 0.1,
  "backend": "dummy"
}
```

### 8. examples/demo_raw_sequence.json

Example raw composer output (happy dance with arm_wave + body_sway + turn_left):
- Must start with `stand_ready` (composer rule: first item is always `stand_ready`)
- Must end with `final_pose` (composer rule: last item is always `final_pose`)
- Total duration should sum to roughly 12 seconds
- Each item: `{"skill": "<name>", "duration": <float>}`

Suggested sequence:
```json
{
  "description": "Raw skill sequence output from RuleBasedDanceComposer for a 12-second happy robot dance",
  "sequence": [
    {"skill": "stand_ready", "duration": 1.0},
    {"skill": "arm_wave", "duration": 2.0},
    {"skill": "body_sway", "duration": 1.5},
    {"skill": "arm_wave", "duration": 2.0},
    {"skill": "step_forward", "duration": 1.5},
    {"skill": "turn_left", "duration": 1.5},
    {"skill": "final_pose", "duration": 2.0}
  ]
}
```

### 9. examples/demo_repaired_sequence.json

Example after TransitionManager repair. Shows:
- All items have `source` field
- `turn_left` (medium risk) has `stand_stable` inserted after it (Rule 10)
- All items are `"agent"` source except the inserted `stand_stable`

```json
{
  "description": "Repaired skill sequence output from TransitionManager — turn_left (medium risk) triggers stand_stable insertion after",
  "sequence": [
    {"skill": "stand_ready", "duration": 1.0, "source": "agent"},
    {"skill": "arm_wave", "duration": 2.0, "source": "agent"},
    {"skill": "body_sway", "duration": 1.5, "source": "agent"},
    {"skill": "arm_wave", "duration": 2.0, "source": "agent"},
    {"skill": "step_forward", "duration": 1.5, "source": "agent"},
    {"skill": "turn_left", "duration": 1.5, "source": "agent"},
    {"skill": "stand_stable", "duration": 0.8, "source": "transition_inserted"},
    {"skill": "final_pose", "duration": 2.0, "source": "agent"}
  ]
}
```

### 10. logs/.gitkeep

Create an empty `logs/.gitkeep` file (zero bytes). This ensures the `logs/` directory is tracked by git while its JSON outputs are ignored.

### 11. All `__init__.py` Files

Every `__init__.py` file must be **completely empty** (zero bytes). No docstrings, no imports, no content of any kind.

### 12. All Empty Module Files

Every `.py` module file listed under "Empty Module Files" must be **completely empty** (zero bytes). These are placeholder files that will be implemented in later tasks. Do NOT add docstrings, imports, or any content.

## Tests to Run

**No tests are run for this task.** The test files (`tests/test_*.py`) are created empty and will be populated in later tasks.

However, you MUST validate the structure after creation:

```bash
# Verify all files exist
find . -type f | sort

# Verify YAML parses correctly
python -c "import yaml; yaml.safe_load(open('/mnt/g/Code/Python/HumaSkill/configs/skills.yaml')); print('skills.yaml: OK')"
python -c "import yaml; yaml.safe_load(open('/mnt/g/Code/Python/HumaSkill/configs/default_config.yaml')); print('default_config.yaml: OK')"

# Verify JSON parses correctly
python -c "import json; json.load(open('/mnt/g/Code/Python/HumaSkill/examples/demo_dance_request.json')); print('demo_dance_request.json: OK')"
python -c "import json; json.load(open('/mnt/g/Code/Python/HumaSkill/examples/demo_raw_sequence.json')); print('demo_raw_sequence.json: OK')"
python -c "import json; json.load(open('/mnt/g/Code/Python/HumaSkill/examples/demo_repaired_sequence.json')); print('demo_repaired_sequence.json: OK')"

# Verify Python can import the package (will succeed for empty modules)
python -c "import humaskill; print('humaskill package: OK')"

# Verify skills.yaml has exactly 12 skills
python -c "
import yaml
data = yaml.safe_load(open('/mnt/g/Code/Python/HumaSkill/configs/skills.yaml'))
print(f'Skill count: {len(data)}')
assert len(data) == 12, f'Expected 12 skills, got {len(data)}'
required_fields = ['name','tags','duration_range','start_pose','end_pose','risk','description','backend','policy_id','checkpoint','action_type','obs_adapter']
for skill in data:
    for field in required_fields:
        assert field in skill, f'Skill {skill[\"name\"]} missing field: {field}'
print('All skills have all required fields: OK')
"
```

## Acceptance Criteria

After completing this task, verify the following:

- [ ] `README.md` exists with project name and one-line description
- [ ] `requirements.txt` contains exactly `pyyaml` and `pytest`
- [ ] `pyproject.toml` is valid TOML, Python >= 3.10, package name `humaskill`
- [ ] `.gitignore` covers Python artifacts and `logs/*.json`
- [ ] `configs/skills.yaml` has exactly 12 skills with ALL required fields (including `backend`, `policy_id`, `checkpoint`, `action_type`, `obs_adapter`)
- [ ] Skills are tagged: `["happy", "dance"]`, `["elegant", "dance"]`, `["power", "dance"]`, `["basic"]`
- [ ] `configs/default_config.yaml` has `fail_prob`, `backend`, `default_duration`, `seed`
- [ ] `examples/demo_dance_request.json`, `demo_raw_sequence.json`, `demo_repaired_sequence.json` are valid JSON
- [ ] `logs/.gitkeep` exists (empty)
- [ ] All `__init__.py` files exist and are empty
- [ ] All empty module files exist and are empty
- [ ] No module files contain any code, imports, or docstrings
- [ ] `scripts/` directory files are NOT created (belong to later tasks)
- [ ] YAML and JSON files parse without errors
- [ ] `humaskill` package is importable (imports without error)

## Constraints and Warnings

- **Follow INTERFACES.md strictly.** Every field in `skills.yaml` must match the `SkillInfo` dataclass definition.
- **Only edit files explicitly allowed.** Do NOT create `scripts/validate_skills.py`, `scripts/run_demo.py`, or any files not in the allowed list.
- **Use Python 3.10+.** All code must be compatible with Python 3.10 or later.
- **Use only PyYAML and pytest.** No other third-party dependencies. No numpy, no requests, no click, no tqdm.
- **Backend returns ExecutionResult.** This is a design constraint for all future implementation — noted here for awareness.
- **Executor logs use `status`.** Log items use `"success"` / `"failed"` strings, never raw result objects.
- **Tests must not assume backend returns raw strings.** Tests validate `ExecutionResult` structure, not string parsing.
- **All empty `.py` files must be truly empty.** Zero bytes. No `# placeholder` comments, no docstrings, no `pass` statements. This is important — later tasks will populate these files, and any pre-existing content could cause merge or logic issues.
- **Do NOT edit any file outside the allowed list.** This includes existing project docs (PROJECT_PLAN.md, INTERFACES.md, etc.) and any files that may already exist in the repository.
