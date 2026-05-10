# HumaSkill — Test Plan

## test_composer.py

### Required Coverage

| # | Test Case | Description |
|---|---|---|
| 1 | `test_starts_with_stand_ready` | Composer output begins with `stand_ready` as first item |
| 2 | `test_ends_with_final_pose` | Composer output ends with `final_pose` as last item |
| 3 | `test_reproducible_with_seed` | Same seed produces identical output sequences |
| 4 | `test_different_seeds_different_output` | Different seeds may produce different outputs (non-deterministic check) |
| 5 | `test_total_duration_close_to_target` | Sum of item durations is within reasonable range of target duration |
| 6 | `test_style_keyword_affects_skill_pool` | Different style keywords (欢快/优雅/力量) select different skill pools |
| 7 | `test_output_is_valid_raw_sequence` | Every output item has `skill` (str) and `duration` (positive float) |
| 8 | `test_empty_text_returns_minimal_sequence` | Empty or minimal text returns at least `stand_ready` + `final_pose` |

---

## test_skill_registry.py

### Required Coverage

| # | Test Case | Description |
|---|---|---|
| 1 | `test_load_skills_yaml` | `skills.yaml` loads successfully, returns non-empty registry |
| 2 | `test_stand_ready_exists` | `stand_ready` is present in the registry |
| 3 | `test_recover_exists` | `recover` is present in the registry |
| 4 | `test_all_names_returns_list` | `all_names()` returns a non-empty list of strings |
| 5 | `test_unknown_skill_raises_error` | Querying a non-existent skill raises `UnknownSkillError` |
| 6 | `test_extended_fields_loaded` | `backend`, `policy_id`, `checkpoint`, `action_type`, `obs_adapter` fields are loaded from YAML |
| 7 | `test_skills_with_tag` | `skills_with_tag("dance")` returns only skills tagged `"dance"` |
| 8 | `test_skill_info_dataclass` | `SkillInfo` is a frozen dataclass with all required fields |

---

## test_transition_manager.py

### Required Coverage

| # | Test Case | Description |
|---|---|---|
| 1 | `test_high_risk_inserts_stand_stable_before` | High risk skill has `stand_stable` inserted before it |
| 2 | `test_high_risk_inserts_stand_stable_after` | High risk skill has `stand_stable` inserted after it |
| 3 | `test_medium_risk_inserts_stand_stable_after` | Medium risk skill has `stand_stable` inserted after it |
| 4 | `test_squat_to_standing_inserts_stand_up` | `squat` (low_pose) → standing skill inserts `stand_up` |
| 5 | `test_duration_clamped` | Out-of-range duration is clamped; source becomes `duration_clamped` |
| 6 | `test_unknown_skill_raises_error` | Referencing an unknown skill raises error |
| 7 | `test_repaired_items_have_required_fields` | Every repaired item has `skill`, `duration`, `source` |
| 8 | `test_any_pose_allows_any_start` | Skills with `start_pose: any` don't trigger pose-based inserts |
| 9 | `test_low_risk_no_inserts` | Low risk skills don't trigger risk-based inserts (besides pose matching) |

---

## test_executor.py

### Required Coverage

| # | Test Case | Description |
|---|---|---|
| 1 | `test_execute_repaired_sequence` | Executor runs a complete repaired sequence through backend |
| 2 | `test_failed_triggers_recover` | When backend returns `failed`, executor inserts `recover` skill |
| 3 | `test_logs_have_full_structure` | Log items contain: `index`, `skill`, `duration`, `source`, `status`, `start_time`, `end_time` |
| 4 | `test_logs_have_backend_fields` | Log items contain: `backend_steps`, `backend_reward`, `failure_reason`, `backend_info` |
| 5 | `test_summary_fields_correct` | Summary has correct total_duration, success_count, failed_count, recover_count |
| 6 | `test_execute_empty_sequence` | Executing an empty sequence returns empty logs (no crash) |

---

## test_backend.py

### Required Coverage

| # | Test Case | Description |
|---|---|---|
| 1 | `test_dummy_backend_returns_execution_result` | `DummyDanceBackend.execute()` returns `ExecutionResult` instance |
| 2 | `test_dummy_backend_default_success` | Default execution returns `status: "success"` |
| 3 | `test_fail_prob_causes_failure` | With `fail_prob=1.0`, execution returns `status: "failed"` |
| 4 | `test_same_seed_reproducible` | Same seed with same `fail_prob` produces reproducible results |
| 5 | `test_status_only_success_or_failed` | `ExecutionResult.status` is always exactly `"success"` or `"failed"` |
| 6 | `test_placeholder_backends_exist` | All 6 placeholder backends (`MotionClipBackend`, `TrainedPolicyBackend`, `MujocoGymBackend`, `IsaacLabBackend`, `TextOpBackend`, `GrootBackend`) are importable classes |
| 7 | `test_base_backend_is_abstract` | `BaseBackend` cannot be instantiated directly |
| 8 | `test_dummy_backend_result_has_correct_skill` | Returned `ExecutionResult.skill` matches the requested skill name |

---

## Test Execution

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
