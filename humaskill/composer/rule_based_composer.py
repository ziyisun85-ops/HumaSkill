"""RuleBasedDanceComposer — rule-based Chinese keyword → skill sequence composer.

Maps Chinese dance style keywords to skill tags and generates
deterministic, seed-reproducible raw skill sequences.
"""

import random
from humaskill.composer.base_composer import BaseComposer
from humaskill.skills.skill_registry import SkillRegistry


class RuleBasedDanceComposer(BaseComposer):
    """Rule-based composer that maps Chinese keywords to skill sequences.

    Detects style keywords in Chinese text, maps them to skill tags,
    and builds a seed-reproducible skill sequence using the skill registry.

    Every sequence:
    - Starts with ``stand_ready``
    - Ends with ``final_pose``
    - Fills the middle with randomly selected skills matching the
      keyword-derived tags
    """

    # Mapping from Chinese keyword to skill tags (additive).
    KEYWORD_TAG_MAP = {
        "\u6b22\u5feb": ["happy"],                  # 欢快
        "\u4f18\u96c5": ["elegant"],                # 优雅
        "\u529b\u91cf": ["power"],                   # 力量
        "\u673a\u5668\u4eba": ["robot"],             # 机器人
        "\u821e\u8e48": ["dance"],                   # 舞蹈
    }

    # Skills that are never selected for the middle fill section.
    _BOOKEND_SKILLS = {"stand_ready", "final_pose"}

    def __init__(self, registry: SkillRegistry) -> None:
        """Initialise with a skill registry for skill lookups.

        Args:
            registry: SkillRegistry instance loaded with skills from
                skills.yaml.
        """
        self._registry = registry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compose(
        self, text: str, duration: float, seed: int | None = None
    ) -> list[dict]:
        """Convert a Chinese instruction into a raw skill sequence.

        Args:
            text: Natural language instruction (Chinese text).
            duration: Target total duration in seconds.
            seed: Optional random seed for reproducibility.

        Returns:
            A list of raw sequence items, each a dict with keys
            ``'skill'`` (str) and ``'duration'`` (float).
        """
        if not text or not text.strip():
            return self._minimal_sequence()

        tags = self._extract_tags(text)
        if not tags:
            # No keyword recognised — return minimal per Rule 10.
            return self._minimal_sequence()

        rng = random.Random(seed)
        return self._build_sequence(tags, duration, rng)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_tags(self, text: str) -> set[str]:
        """Detect Chinese keywords in *text* and return the union of
        their mapped tags.

        Args:
            text: Input text to scan for keywords.

        Returns:
            Set of tag strings derived from matched keywords.
        """
        tags: set[str] = set()
        for keyword, mapped_tags in self.KEYWORD_TAG_MAP.items():
            if keyword in text:
                tags.update(mapped_tags)
        return tags

    def _build_sequence(
        self, tags: set[str], target_duration: float, rng: random.Random
    ) -> list[dict]:
        """Build the full raw sequence from bookends + middle fill.

        Args:
            tags: Skill tags to use for middle fill candidate selection.
            target_duration: Desired total sequence duration in seconds.
            rng: Seeded ``random.Random`` instance.

        Returns:
            Raw sequence list: ``[stand_ready, …, final_pose]``.
        """
        stand_ready_dur = self._midpoint_duration("stand_ready")
        final_pose_dur = self._midpoint_duration("final_pose")

        bookend_total = stand_ready_dur + final_pose_dur
        middle_pool = self._build_middle_pool(tags)

        # Bookend items (always present).
        start_item = {"skill": "stand_ready", "duration": stand_ready_dur}
        end_item = {"skill": "final_pose", "duration": final_pose_dur}

        # Nothing to fill with — return minimal sequence.
        if not middle_pool:
            return [start_item, end_item]

        middle_items: list[dict] = []
        middle_total = 0.0

        # Keep filling until we are within ±3 s of target or would
        # overshoot by more than 3 s.
        while middle_pool:
            skill_name = rng.choice(list(middle_pool))
            skill_dur = self._midpoint_duration(skill_name)
            new_total = bookend_total + middle_total + skill_dur

            if new_total > target_duration + 3.0:
                break   # would overshoot too far

            middle_items.append({"skill": skill_name, "duration": skill_dur})
            middle_total += skill_dur

            if abs(bookend_total + middle_total - target_duration) <= 3.0:
                break   # close enough

        return [start_item, *middle_items, end_item]

    def _build_middle_pool(self, tags: set[str]) -> set[str]:
        """Collect skill names matching any of *tags*, excluding bookends.

        Args:
            tags: Set of tags to filter by.

        Returns:
            Set of skill name strings eligible for middle fill.
        """
        pool: set[str] = set()
        for tag in tags:
            for skill in self._registry.skills_with_tag(tag):
                if skill.name not in self._BOOKEND_SKILLS:
                    pool.add(skill.name)
        return pool

    def _midpoint_duration(self, skill_name: str) -> float:
        """Return the midpoint of a skill's ``duration_range``.

        Args:
            skill_name: Registered skill name.

        Returns:
            ``(min + max) / 2`` for the skill's duration range.
        """
        info = self._registry.get(skill_name)
        return (info.duration_range[0] + info.duration_range[1]) / 2.0

    def _minimal_sequence(self) -> list[dict]:
        """Return a minimal sequence with only the two bookend skills."""
        return [
            {"skill": "stand_ready",
             "duration": self._midpoint_duration("stand_ready")},
            {"skill": "final_pose",
             "duration": self._midpoint_duration("final_pose")},
        ]
