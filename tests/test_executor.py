"""Tests for HumaSkill SkillExecutor.

Covers all 6 test cases from TEST_PLAN.md test_executor section.
Tests must NOT assume backend returns raw strings — use ExecutionResult.status.
"""

from pathlib import Path
import sys
import os

import pytest

from humaskill.skills.skill_registry import SkillRegistry
from humaskill.backends.dummy_backend import DummyDanceBackend
from humaskill.harness.skill_executor import SkillExecutor


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "configs"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def registry() -> SkillRegistry:
    """Load the real skills.yaml registry once per test module."""
    return SkillRegistry(str(CONFIG_DIR / "skills.yaml"))


@pytest.fixture
def dummy_backend() -> DummyDanceBackend:
    """DummyDanceBackend with default fail_prob=0.0 (always succeeds)."""
    return DummyDanceBackend(fail_prob=0.0, seed=42)


@pytest.fixture
def failing_backend() -> DummyDanceBackend:
    """DummyDanceBackend with fail_prob=1.0 (always fails)."""
    return DummyDanceBackend(fail_prob=1.0, seed=42)


@pytest.fixture
def sample_sequence() -> list[dict]:
    """A simple repaired sequence for testing."""
    return [
        {"skill": "stand_ready", "duration": 1.0, "source": "agent"},
        {"skill": "arm_wave", "duration": 1.5, "source": "agent"},
        {"skill": "final_pose", "duration": 1.0, "source": "agent"},
    ]


# ---------------------------------------------------------------------------
# Test 1: Execute a complete repaired sequence
# ---------------------------------------------------------------------------

def test_execute_repaired_sequence(
    registry: SkillRegistry,
    dummy_backend: DummyDanceBackend,
    sample_sequence: list[dict],
):
    """Executor runs a complete repaired sequence through a backend.

    Verify: logs is non-empty list, each log entry has all required fields.
    """
    executor = SkillExecutor(dummy_backend, registry)
    logs, summary = executor.execute_sequence(sample_sequence)

    # Non-empty.
    assert isinstance(logs, list), "logs must be a list"
    assert len(logs) > 0, "logs must not be empty"

    required_fields = [
        "index", "skill", "duration", "source", "status",
        "start_time", "end_time",
        "backend_steps", "backend_reward", "failure_reason", "backend_info",
    ]

    for entry in logs:
        assert isinstance(entry, dict), f"log entry must be a dict, got {type(entry)}"
        for field in required_fields:
            assert field in entry, f"log entry missing field: {field!r}"


# ---------------------------------------------------------------------------
# Test 2: Failed execution triggers recovery
# ---------------------------------------------------------------------------

def test_failed_triggers_recover(
    registry: SkillRegistry,
    failing_backend: DummyDanceBackend,
    sample_sequence: list[dict],
):
    """When backend returns 'failed', executor inserts a recover skill and retries.

    Verify: at least one log entry has skill='recover' and source='recovery_inserted'.
    The failed skill appears at least twice in logs.
    """
    executor = SkillExecutor(failing_backend, registry)
    logs, summary = executor.execute_sequence(sample_sequence)

    # Must have at least one recovery entry.
    recover_entries = [
        e for e in logs
        if e["skill"] == "recover" and e["source"] == "recovery_inserted"
    ]
    assert len(recover_entries) > 0, (
        "Expected at least one recovery_inserted recover entry"
    )

    # The failed skill should appear more than once (original + retry).
    # Since fail_prob=1.0, at least one skill in the sequence will fail.
    skill_counts: dict[str, int] = {}
    for e in logs:
        skill = e["skill"]
        if skill != "recover":  # don't count recover itself
            skill_counts[skill] = skill_counts.get(skill, 0) + 1

    # At least one non-recover skill should appear twice.
    assert any(c >= 2 for c in skill_counts.values()), (
        f"No skill appeared twice (original + retry): {skill_counts}"
    )

    # Summary should reflect recovery.
    assert summary["recover_count"] > 0, (
        f"recover_count must be > 0, got {summary['recover_count']}"
    )


# ---------------------------------------------------------------------------
# Test 3: Logs have full structure (7 required fields)
# ---------------------------------------------------------------------------

def test_logs_have_full_structure(
    registry: SkillRegistry,
    dummy_backend: DummyDanceBackend,
    sample_sequence: list[dict],
):
    """Every log item contains: index, skill, duration, source, status,
    start_time, end_time."""
    executor = SkillExecutor(dummy_backend, registry)
    logs, _ = executor.execute_sequence(sample_sequence)

    core_fields = ["index", "skill", "duration", "source", "status",
                   "start_time", "end_time"]

    for entry in logs:
        for field in core_fields:
            assert field in entry, f"log entry missing core field: {field!r}"

    # Also verify types / sensible values.
    for entry in logs:
        assert isinstance(entry["index"], int)
        assert isinstance(entry["skill"], str)
        assert isinstance(entry["duration"], float)
        assert isinstance(entry["source"], str)
        assert entry["status"] in ("success", "failed")
        assert isinstance(entry["start_time"], float)
        assert isinstance(entry["end_time"], float)
        assert entry["end_time"] >= entry["start_time"]


# ---------------------------------------------------------------------------
# Test 4: Logs have backend fields (4 required fields)
# ---------------------------------------------------------------------------

def test_logs_have_backend_fields(
    registry: SkillRegistry,
    dummy_backend: DummyDanceBackend,
    sample_sequence: list[dict],
):
    """Every log item contains: backend_steps, backend_reward, failure_reason,
    backend_info."""
    executor = SkillExecutor(dummy_backend, registry)
    logs, _ = executor.execute_sequence(sample_sequence)

    backend_fields = ["backend_steps", "backend_reward", "failure_reason", "backend_info"]

    for entry in logs:
        for field in backend_fields:
            assert field in entry, f"log entry missing backend field: {field!r}"

    # Type checks.
    for entry in logs:
        assert isinstance(entry["backend_steps"], int)
        # backend_reward can be None or float
        assert entry["backend_reward"] is None or isinstance(entry["backend_reward"], float)
        # failure_reason can be None or str
        assert entry["failure_reason"] is None or isinstance(entry["failure_reason"], str)
        assert isinstance(entry["backend_info"], dict)


# ---------------------------------------------------------------------------
# Test 5: Summary fields are correct
# ---------------------------------------------------------------------------

def test_summary_fields_correct(
    registry: SkillRegistry,
    dummy_backend: DummyDanceBackend,
    sample_sequence: list[dict],
):
    """Summary has total_items, total_duration, planned_duration, success_count,
    failed_count, recover_count, backend_name. Counts are consistent with logs."""
    executor = SkillExecutor(dummy_backend, registry)
    logs, summary = executor.execute_sequence(sample_sequence)

    required_keys = [
        "total_items", "total_duration", "planned_duration",
        "success_count", "failed_count", "recover_count", "backend_name",
    ]
    for key in required_keys:
        assert key in summary, f"summary missing key: {key!r}"

    # Consistency checks.
    assert summary["total_items"] == len(logs)
    assert summary["success_count"] == sum(1 for e in logs if e["status"] == "success")
    assert summary["failed_count"] == sum(1 for e in logs if e["status"] == "failed")
    assert summary["backend_name"] == "DummyDanceBackend"

    # planned_duration should be sum of input sequence durations.
    expected_planned = sum(item["duration"] for item in sample_sequence)
    assert summary["planned_duration"] == pytest.approx(expected_planned)

    # total_duration should be >= planned_duration (may include recovery inserts).
    assert summary["total_duration"] >= summary["planned_duration"] - 0.001


# ---------------------------------------------------------------------------
# Test 6: Empty sequence returns empty logs (no crash)
# ---------------------------------------------------------------------------

def test_execute_empty_sequence(
    registry: SkillRegistry,
    dummy_backend: DummyDanceBackend,
):
    """Executing an empty sequence returns empty logs [] and a zeroed summary."""
    executor = SkillExecutor(dummy_backend, registry)
    logs, summary = executor.execute_sequence([])

    assert logs == [], f"Expected empty list, got {logs}"
    assert summary["total_items"] == 0
    assert summary["total_duration"] == 0.0
    assert summary["planned_duration"] == 0.0
    assert summary["success_count"] == 0
    assert summary["failed_count"] == 0
    assert summary["recover_count"] == 0
    assert summary["backend_name"] == "DummyDanceBackend"


# ---------------------------------------------------------------------------
# Extra: source field defaults to "agent" if missing
# ---------------------------------------------------------------------------

def test_source_defaults_to_agent(
    registry: SkillRegistry,
    dummy_backend: DummyDanceBackend,
):
    """Items without a source field default to 'agent'."""
    executor = SkillExecutor(dummy_backend, registry)
    seq = [{"skill": "arm_wave", "duration": 1.0}]  # no source field
    logs, _ = executor.execute_sequence(seq)
    assert len(logs) == 1
    assert logs[0]["source"] == "agent"


# ---------------------------------------------------------------------------
# Extra: recovery uses registry recover duration midpoint
# ---------------------------------------------------------------------------

def test_recover_uses_registry_duration(
    registry: SkillRegistry,
    failing_backend: DummyDanceBackend,
):
    """Recovery uses the recover skill's duration_range midpoint from registry."""
    executor = SkillExecutor(failing_backend, registry)
    seq = [{"skill": "arm_wave", "duration": 1.0, "source": "agent"}]
    logs, _ = executor.execute_sequence(seq)

    recover_skill = registry.get("recover")
    expected_mid = (recover_skill.duration_range[0] + recover_skill.duration_range[1]) / 2.0

    recover_entries = [e for e in logs if e["skill"] == "recover"]
    assert len(recover_entries) > 0
    for re in recover_entries:
        assert re["duration"] == pytest.approx(expected_mid)
