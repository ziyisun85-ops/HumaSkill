"""Tests for HumaSkill backends.

Covers all 8 test cases from TEST_PLAN.md test_backend section.
Tests must NOT assume backends return raw strings — use ExecutionResult.status.
"""

import pytest

from humaskill.backends.base_backend import BaseBackend, ExecutionResult
from humaskill.backends.dummy_backend import DummyDanceBackend
from humaskill.backends.motion_clip_backend import MotionClipBackend
from humaskill.backends.trained_policy_backend import TrainedPolicyBackend
from humaskill.backends.mujoco_gym_backend import MujocoGymBackend
from humaskill.backends.isaaclab_backend import IsaacLabBackend
from humaskill.backends.textop_backend import TextOpBackend
from humaskill.backends.groot_backend import GrootBackend


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def dummy_backend():
    """DummyDanceBackend with default fail_prob=0.0 (always succeeds)."""
    return DummyDanceBackend(fail_prob=0.0, seed=42)


# ---------------------------------------------------------------------------
# Test 1: DummyDanceBackend.execute() returns ExecutionResult instance
# ---------------------------------------------------------------------------

def test_dummy_backend_returns_execution_result(dummy_backend):
    """DummyDanceBackend.execute() returns an ExecutionResult, not a dict or string."""
    result = dummy_backend.execute("arm_wave", 1.5)
    assert isinstance(result, ExecutionResult), (
        f"Expected ExecutionResult, got {type(result).__name__}"
    )


# ---------------------------------------------------------------------------
# Test 2: Default execution returns success
# ---------------------------------------------------------------------------

def test_dummy_backend_default_success(dummy_backend):
    """With default fail_prob=0.0, execution returns status 'success'."""
    result = dummy_backend.execute("arm_wave", 1.5)
    assert result.status == "success", (
        f"Expected 'success', got {result.status!r}"
    )


# ---------------------------------------------------------------------------
# Test 3: fail_prob=1.0 causes failure
# ---------------------------------------------------------------------------

def test_fail_prob_causes_failure():
    """With fail_prob=1.0, execution returns status 'failed'."""
    backend = DummyDanceBackend(fail_prob=1.0, seed=42)
    result = backend.execute("arm_wave", 1.5)
    assert result.status == "failed", (
        f"Expected 'failed', got {result.status!r}"
    )


# ---------------------------------------------------------------------------
# Test 4: Same seed + same fail_prob produces reproducible results
# ---------------------------------------------------------------------------

def test_same_seed_reproducible():
    """Same seed with same fail_prob produces identical results across runs."""
    skills = ["arm_wave", "turn_left", "squat", "step_forward"]

    b1 = DummyDanceBackend(fail_prob=0.5, seed=99)
    b2 = DummyDanceBackend(fail_prob=0.5, seed=99)

    for skill in skills:
        r1 = b1.execute(skill, 1.0)
        r2 = b2.execute(skill, 1.0)
        assert r1.status == r2.status, (
            f"Reproducibility broken for '{skill}': "
            f"{r1.status} vs {r2.status}"
        )
        assert r1.failure_reason == r2.failure_reason


# ---------------------------------------------------------------------------
# Test 5: status is always exactly "success" or "failed"
# ---------------------------------------------------------------------------

def test_status_only_success_or_failed():
    """ExecutionResult.status is only 'success' or 'failed' for all fail_probs."""
    fail_probs = [0.0, 0.5, 1.0]
    for fp in fail_probs:
        backend = DummyDanceBackend(fail_prob=fp, seed=42)
        # Run many skills to ensure we see both cases.
        for skill in ["arm_wave", "turn_left", "squat", "step_forward", "body_sway"]:
            result = backend.execute(skill, 1.0)
            assert result.status in ("success", "failed"), (
                f"Invalid status {result.status!r} for fail_prob={fp}, skill={skill}"
            )
            assert result.status != "", "status should not be empty string"
            # If failed, failure_reason must be set.
            if result.status == "failed":
                assert result.failure_reason is not None, (
                    "failure_reason must be set when status is 'failed'"
                )


# ---------------------------------------------------------------------------
# Test 6: All 6 placeholder backends exist and are proper subclasses
# ---------------------------------------------------------------------------

PLACEHOLDERS = [
    MotionClipBackend,
    TrainedPolicyBackend,
    MujocoGymBackend,
    IsaacLabBackend,
    TextOpBackend,
    GrootBackend,
]


def test_placeholder_backends_exist():
    """All 6 placeholders are importable, subclass BaseBackend, and raise on execute."""
    for cls in PLACEHOLDERS:
        # Must be a subclass of BaseBackend.
        assert issubclass(cls, BaseBackend), (
            f"{cls.__name__} must be a subclass of BaseBackend"
        )
        # Must raise NotImplementedError on execute().
        instance = cls()
        with pytest.raises(NotImplementedError):
            instance.execute("arm_wave", 1.0)


# ---------------------------------------------------------------------------
# Test 7: BaseBackend is abstract (cannot instantiate directly)
# ---------------------------------------------------------------------------

def test_base_backend_is_abstract():
    """BaseBackend cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseBackend()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Test 8: ExecutionResult has correct skill and duration
# ---------------------------------------------------------------------------

def test_dummy_backend_result_has_correct_skill(dummy_backend):
    """Returned ExecutionResult.skill matches requested skill name and duration."""
    for skill in ["arm_wave", "turn_left", "squat"]:
        result = dummy_backend.execute(skill, 2.0)
        assert result.skill == skill, (
            f"Expected skill={skill!r}, got {result.skill!r}"
        )
        assert result.duration == 2.0, (
            f"Expected duration=2.0, got {result.duration}"
        )


# ---------------------------------------------------------------------------
# Extra: DummyDanceBackend input validation
# ---------------------------------------------------------------------------

def test_dummy_backend_raises_on_invalid_fail_prob():
    """fail_prob outside [0, 1] raises ValueError."""
    with pytest.raises(ValueError):
        DummyDanceBackend(fail_prob=-0.1)
    with pytest.raises(ValueError):
        DummyDanceBackend(fail_prob=1.5)


def test_dummy_backend_raises_on_empty_skill_name():
    """Empty skill_name raises ValueError."""
    backend = DummyDanceBackend(fail_prob=0.0)
    with pytest.raises(ValueError):
        backend.execute("", 1.0)


def test_dummy_backend_raises_on_nonpositive_duration():
    """Zero or negative duration raises ValueError."""
    backend = DummyDanceBackend(fail_prob=0.0)
    with pytest.raises(ValueError):
        backend.execute("arm_wave", 0.0)
    with pytest.raises(ValueError):
        backend.execute("arm_wave", -1.0)


# ---------------------------------------------------------------------------
# Extra: High-fail skills have measurably higher failure rates
# ---------------------------------------------------------------------------

def test_high_fail_skills_fail_more():
    """turn_left, turn_right, squat fail more than arm_wave at moderate fail_prob."""
    backend = DummyDanceBackend(fail_prob=0.3, seed=42)

    # Run many trials on a normal skill.
    normal_fails = sum(
        1 for _ in range(200)
        if backend.execute("arm_wave", 1.0).status == "failed"
    )
    # Run many trials on a high-fail skill.
    high_fails = sum(
        1 for _ in range(200)
        if backend.execute("turn_left", 1.0).status == "failed"
    )

    # High-fail skill should fail more (2.5x multiplier at 0.3 = 0.75 effective).
    assert high_fails > normal_fails, (
        f"High-fail skills should fail more: normal={normal_fails}, high={high_fails}"
    )
