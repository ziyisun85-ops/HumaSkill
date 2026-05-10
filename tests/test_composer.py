"""Tests for HumaSkill composer module.

Covers all 8 test cases from TEST_PLAN.md test_composer section.
"""

from pathlib import Path

import pytest

from humaskill.composer.base_composer import BaseComposer
from humaskill.composer.rule_based_composer import RuleBasedDanceComposer
from humaskill.composer.llm_composer import LLMComposer
from humaskill.skills.skill_registry import SkillRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CONFIG_DIR = Path(__file__).resolve().parent.parent / "configs"


@pytest.fixture(scope="module")
def registry() -> SkillRegistry:
    """Load the real skills.yaml registry once per test module."""
    return SkillRegistry(str(CONFIG_DIR / "skills.yaml"))


@pytest.fixture(scope="module")
def composer(registry: SkillRegistry) -> RuleBasedDanceComposer:
    """Create a RuleBasedDanceComposer wired to the loaded registry."""
    return RuleBasedDanceComposer(registry)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _middle_skills(seq: list[dict]) -> list[str]:
    """Return skill names from the middle of a sequence (strip bookends)."""
    if len(seq) <= 2:
        return []
    return [item["skill"] for item in seq[1:-1]]


def _total_duration(seq: list[dict]) -> float:
    """Sum of all item durations in a raw sequence."""
    return sum(item["duration"] for item in seq)


# ---------------------------------------------------------------------------
# Test 1: Starts with stand_ready
# ---------------------------------------------------------------------------

def test_starts_with_stand_ready(composer: RuleBasedDanceComposer) -> None:
    """Composer output must begin with stand_ready as the first item."""
    seq = composer.compose("\u6b22\u5feb\u821e\u8e48", duration=12.0, seed=42)
    assert seq[0]["skill"] == "stand_ready"


# ---------------------------------------------------------------------------
# Test 2: Ends with final_pose
# ---------------------------------------------------------------------------

def test_ends_with_final_pose(composer: RuleBasedDanceComposer) -> None:
    """Composer output must end with final_pose as the last item."""
    seq = composer.compose("\u6b22\u5feb\u821e\u8e48", duration=12.0, seed=42)
    assert seq[-1]["skill"] == "final_pose"


# ---------------------------------------------------------------------------
# Test 3: Reproducible with seed
# ---------------------------------------------------------------------------

def test_reproducible_with_seed(composer: RuleBasedDanceComposer) -> None:
    """Same seed + same inputs must produce identical output sequences."""
    kwargs = {"text": "\u6b22\u5feb\u821e\u8e48", "duration": 12.0, "seed": 42}
    seq1 = composer.compose(**kwargs)
    seq2 = composer.compose(**kwargs)
    assert seq1 == seq2


# ---------------------------------------------------------------------------
# Test 4: Different seeds produce different output
# ---------------------------------------------------------------------------

def test_different_seeds_different_output(
    composer: RuleBasedDanceComposer,
) -> None:
    """Different seeds should produce different sequences for diverse pools.

    Uses 'elegant' keyword (\u4f18\u96c5) which has a pool of 3 skills
    (body_sway, turn_left, turn_right).  With 12 s of fill the chance of
    collision between two well-separated seeds is negligible.
    """
    seq42 = composer.compose("\u4f18\u96c5\u821e\u8e48", duration=12.0, seed=42)
    seq99 = composer.compose("\u4f18\u96c5\u821e\u8e48", duration=12.0, seed=999)
    assert seq42 != seq99, (
        "Different seeds produced identical sequences; "
        "this is extremely unlikely with pool size 3"
    )


# ---------------------------------------------------------------------------
# Test 5: Total duration close to target
# ---------------------------------------------------------------------------

def test_total_duration_close_to_target(
    composer: RuleBasedDanceComposer,
) -> None:
    """Sum of item durations must be within ±3 s of the target duration."""
    target = 12.0
    seq = composer.compose("\u6b22\u5feb\u821e\u8e48", duration=target, seed=42)
    total = _total_duration(seq)
    assert abs(total - target) <= 3.0, (
        f"total={total} not within ±3 of target={target}"
    )


# ---------------------------------------------------------------------------
# Test 6: Style keyword affects skill pool
# ---------------------------------------------------------------------------

def test_style_keyword_affects_skill_pool(
    composer: RuleBasedDanceComposer,
) -> None:
    """Different keywords select different skill tags → different middle skills."""
    seq_happy = composer.compose("\u6b22\u5feb", duration=12.0, seed=42)
    seq_elegant = composer.compose("\u4f18\u96c5", duration=12.0, seed=42)
    seq_power = composer.compose("\u529b\u91cf", duration=12.0, seed=42)

    happy_middle = set(_middle_skills(seq_happy))
    elegant_middle = set(_middle_skills(seq_elegant))
    power_middle = set(_middle_skills(seq_power))

    # These pools should be disjoint given the current skills.yaml tags.
    assert happy_middle != elegant_middle, "happy vs elegant pools should differ"
    assert happy_middle != power_middle, "happy vs power pools should differ"
    assert elegant_middle != power_middle, "elegant vs power pools should differ"


# ---------------------------------------------------------------------------
# Test 7: Output is a valid raw sequence
# ---------------------------------------------------------------------------

def test_output_is_valid_raw_sequence(
    composer: RuleBasedDanceComposer, registry: SkillRegistry
) -> None:
    """Every item must have 'skill' (str) and 'duration' (positive float).

    All skill names must exist in the registry.
    """
    seq = composer.compose("\u6b22\u5feb\u821e\u8e48", duration=12.0, seed=42)
    assert len(seq) >= 2

    for item in seq:
        # Exactly two keys.
        assert set(item.keys()) == {"skill", "duration"}, (
            f"Unexpected keys: {set(item.keys())}"
        )
        # Correct types and values.
        assert isinstance(item["skill"], str), f"skill not str: {item['skill']!r}"
        assert isinstance(item["duration"], float), (
            f"duration not float: {item['duration']!r}"
        )
        assert item["duration"] > 0.0
        # Skill must be registered.
        assert registry.has(item["skill"]), (
            f"Unknown skill in sequence: {item['skill']}"
        )


# ---------------------------------------------------------------------------
# Test 8: Empty / minimal text returns minimal sequence
# ---------------------------------------------------------------------------

def test_empty_text_returns_minimal_sequence(
    composer: RuleBasedDanceComposer, registry: SkillRegistry
) -> None:
    """Empty text (or text with no recognised keywords) should return
    just [stand_ready, final_pose] — exactly two items."""
    # Truly empty
    seq_empty = composer.compose("", duration=12.0, seed=42)
    assert len(seq_empty) == 2
    assert seq_empty[0]["skill"] == "stand_ready"
    assert seq_empty[1]["skill"] == "final_pose"

    # Whitespace only
    seq_spaces = composer.compose("   ", duration=12.0, seed=42)
    assert len(seq_spaces) == 2
    assert seq_spaces[0]["skill"] == "stand_ready"
    assert seq_spaces[1]["skill"] == "final_pose"

    # No recognised keyword
    seq_unknown = composer.compose("\u4e00\u4e9b\u65e0\u5173\u7684\u6587\u672c", duration=12.0, seed=42)
    assert len(seq_unknown) == 2
    assert seq_unknown[0]["skill"] == "stand_ready"
    assert seq_unknown[1]["skill"] == "final_pose"


# ---------------------------------------------------------------------------
# Extra: BaseComposer is abstract, LLMComposer raises NotImplementedError
# ---------------------------------------------------------------------------

def test_base_composer_is_abstract() -> None:
    """BaseComposer cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseComposer()  # type: ignore[abstract]


def test_llm_composer_raises_not_implemented() -> None:
    """LLMComposer.compose() must raise NotImplementedError."""
    c = LLMComposer()
    with pytest.raises(NotImplementedError):
        c.compose("dance", duration=12.0)
