"""Tests for TransitionManager — all 9 test cases from TEST_PLAN.md."""

import pytest

from humaskill.skills.skill_registry import SkillRegistry
from humaskill.harness.transition_manager import TransitionManager
from humaskill.utils.errors import UnknownSkillError


@pytest.fixture(scope="module")
def registry():
    """Load the skill registry once for all tests in this module."""
    return SkillRegistry("configs/skills.yaml")


@pytest.fixture
def transition_manager(registry):
    """Create a TransitionManager with the loaded registry."""
    return TransitionManager(registry)


# ── helpers ──────────────────────────────────────────────────────────

def _has_inserted(sequence: list[dict], skill_name: str) -> bool:
    """Return True if *sequence* contains a transition-inserted item
    with the given *skill_name*."""
    for item in sequence:
        if (item["skill"] == skill_name
                and item.get("source") == "transition_inserted"):
            return True
    return False


def _item_before(sequence: list[dict], skill_name: str, before_skill: str) -> bool:
    """Return True if *skill_name* appears immediately before *before_skill*."""
    for i in range(len(sequence) - 1):
        if (sequence[i]["skill"] == skill_name
                and sequence[i + 1]["skill"] == before_skill):
            return True
    return False


def _item_after(sequence: list[dict], skill_name: str, after_skill: str) -> bool:
    """Return True if *skill_name* appears immediately after *after_skill*."""
    for i in range(len(sequence) - 1):
        if (sequence[i]["skill"] == after_skill
                and sequence[i + 1]["skill"] == skill_name):
            return True
    return False


# ── Test 1 ───────────────────────────────────────────────────────────

def test_high_risk_inserts_stand_stable_before(transition_manager):
    """High risk skill (squat) has stand_stable inserted before it."""
    raw = [{"skill": "squat", "duration": 1.5}]
    repaired = transition_manager.repair(raw)

    assert _item_before(repaired, "stand_stable", "squat"), \
        "Expected stand_stable immediately before squat"


# ── Test 2 ───────────────────────────────────────────────────────────

def test_high_risk_inserts_stand_stable_after(transition_manager):
    """High risk skill (squat) has stand_stable inserted after it."""
    raw = [{"skill": "squat", "duration": 1.5}]
    repaired = transition_manager.repair(raw)

    assert _item_after(repaired, "stand_stable", "squat"), \
        "Expected stand_stable immediately after squat"


# ── Test 3 ───────────────────────────────────────────────────────────

def test_medium_risk_inserts_stand_stable_after(transition_manager):
    """Medium risk skill (turn_left) has stand_stable inserted after it."""
    raw = [{"skill": "turn_left", "duration": 1.0}]
    repaired = transition_manager.repair(raw)

    assert _item_after(repaired, "stand_stable", "turn_left"), \
        "Expected stand_stable immediately after turn_left"


# ── Test 4 ───────────────────────────────────────────────────────────

def test_squat_to_standing_inserts_stand_up(transition_manager):
    """squat (low_pose) → standing skill inserts stand_up between them."""
    raw = [
        {"skill": "squat", "duration": 1.5},
        {"skill": "arm_wave", "duration": 1.0},
    ]
    repaired = transition_manager.repair(raw)

    # stand_up should appear somewhere between squat and arm_wave
    assert _has_inserted(repaired, "stand_up"), \
        "Expected a transition-inserted stand_up in the repaired sequence"

    # Verify ordering: stand_up appears after squat and before arm_wave
    squat_idx = None
    stand_up_idx = None
    arm_wave_idx = None
    for i, item in enumerate(repaired):
        if item["skill"] == "squat":
            squat_idx = i
        elif item["skill"] == "stand_up":
            stand_up_idx = i
        elif item["skill"] == "arm_wave":
            arm_wave_idx = i

    assert squat_idx is not None
    assert stand_up_idx is not None
    assert arm_wave_idx is not None
    assert squat_idx < stand_up_idx < arm_wave_idx, \
        "stand_up must appear after squat and before arm_wave"


# ── Test 5 ───────────────────────────────────────────────────────────

def test_duration_clamped(transition_manager):
    """Out-of-range duration is clamped; source becomes duration_clamped."""
    raw = [{"skill": "arm_wave", "duration": 10.0}]  # range [0.5, 3.0]
    repaired = transition_manager.repair(raw)

    arm_wave_item = None
    for item in repaired:
        if item["skill"] == "arm_wave":
            arm_wave_item = item
            break

    assert arm_wave_item is not None, "arm_wave not found in output"
    assert arm_wave_item["duration"] == 3.0, \
        f"Expected clamped duration 3.0, got {arm_wave_item['duration']}"
    assert arm_wave_item["source"] == "duration_clamped", \
        f"Expected source 'duration_clamped', got {arm_wave_item['source']}"


def test_duration_clamped_below_min(transition_manager):
    """Below-minimum duration is clamped up; source becomes duration_clamped."""
    raw = [{"skill": "arm_wave", "duration": 0.1}]  # range [0.5, 3.0]
    repaired = transition_manager.repair(raw)

    arm_wave_item = None
    for item in repaired:
        if item["skill"] == "arm_wave":
            arm_wave_item = item
            break

    assert arm_wave_item is not None
    assert arm_wave_item["duration"] == 0.5
    assert arm_wave_item["source"] == "duration_clamped"


# ── Test 6 ───────────────────────────────────────────────────────────

def test_unknown_skill_raises_error(transition_manager):
    """Referencing a skill not in the registry raises UnknownSkillError."""
    raw = [{"skill": "nonexistent_skill_xyz", "duration": 1.0}]
    with pytest.raises(UnknownSkillError):
        transition_manager.repair(raw)


# ── Test 7 ───────────────────────────────────────────────────────────

def test_repaired_items_have_required_fields(transition_manager):
    """Every repaired item has skill, duration, source with correct types."""
    raw = [
        {"skill": "stand_ready", "duration": 1.0},
        {"skill": "arm_wave", "duration": 2.0},
        {"skill": "squat", "duration": 1.5},
        {"skill": "turn_left", "duration": 1.0},
        {"skill": "final_pose", "duration": 2.0},
    ]
    repaired = transition_manager.repair(raw)

    assert len(repaired) > 0, "Repaired sequence must not be empty"

    for i, item in enumerate(repaired):
        # Rule 12: Every item must have 'skill', 'duration', 'source'
        assert "skill" in item, f"Item {i} missing 'skill' key: {item}"
        assert "duration" in item, f"Item {i} missing 'duration' key: {item}"
        assert "source" in item, f"Item {i} missing 'source' key: {item}"

        assert isinstance(item["skill"], str), \
            f"Item {i}: 'skill' must be str, got {type(item['skill'])}"
        assert item["skill"] != "", f"Item {i}: 'skill' must be non-empty"

        assert isinstance(item["duration"], (int, float)), \
            f"Item {i}: 'duration' must be number, got {type(item['duration'])}"
        assert item["duration"] > 0, \
            f"Item {i}: 'duration' must be positive, got {item['duration']}"

        assert item["source"] in (
            "agent", "transition_inserted", "recovery_inserted", "duration_clamped"
        ), f"Item {i}: invalid source value '{item['source']}'"


# ── Test 8 ───────────────────────────────────────────────────────────

def test_any_pose_allows_any_start(transition_manager):
    """Skills with start_pose: any don't trigger pose-based inserts."""
    # recover has start_pose="any" — even after squat (low_pose),
    # no stand_up should be inserted for recover.
    raw = [
        {"skill": "squat", "duration": 1.5},
        {"skill": "recover", "duration": 1.5},
    ]
    repaired = transition_manager.repair(raw)

    # stand_up should NOT appear (recover accepts any pose)
    for item in repaired:
        if item.get("source") == "transition_inserted" and item["skill"] == "stand_up":
            # It's OK if stand_up was inserted for some other reason,
            # but it should NOT be between squat and recover.
            # Find positions
            pass

    # Check that no stand_up appears after squat and before recover
    squat_idx = None
    recover_idx = None
    for i, item in enumerate(repaired):
        if item["skill"] == "squat":
            squat_idx = i
        elif item["skill"] == "recover":
            recover_idx = i

    assert squat_idx is not None
    assert recover_idx is not None

    between = repaired[squat_idx + 1:recover_idx]
    skills_between = [item["skill"] for item in between]
    assert "stand_up" not in skills_between, \
        f"stand_up should not appear between squat and recover (any pose), got {skills_between}"


# ── Test 9 ───────────────────────────────────────────────────────────

def test_low_risk_no_inserts(transition_manager):
    """Low risk skills don't trigger risk-based inserts (Rules 8–10)."""
    raw = [
        {"skill": "arm_wave", "duration": 1.0},
        {"skill": "body_sway", "duration": 1.0},
    ]
    repaired = transition_manager.repair(raw)

    # Both are low risk; no risk-based inserts should appear.
    # The only inserts allowed would be pose-matching inserts (Rules 4-7),
    # but arm_wave.end_pose=standing and body_sway.start_pose=standing match.
    # So no inserts at all expected.
    agent_items = [item for item in repaired if item["source"] == "agent"]
    assert len(agent_items) == 2, \
        f"Expected 2 agent items, got {len(agent_items)}"

    transition_items = [item for item in repaired
                        if item["source"] == "transition_inserted"]
    assert len(transition_items) == 0, \
        f"Expected no transition_inserted items for low-risk matching poses, " \
        f"got {[it['skill'] for it in transition_items]}"
