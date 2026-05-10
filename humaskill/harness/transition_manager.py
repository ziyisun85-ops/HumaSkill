"""TransitionManager — repairs skill sequences for safe, executable transitions.

Implements all 12 transition repair rules from INTERFACES.md §11.
"""

from copy import deepcopy

from humaskill.skills.skill_registry import SkillRegistry
from humaskill.skills.skill_info import SkillInfo

# Default insert durations (INTERFACES.md §11)
_STAND_STABLE_DURATION = 0.8
_STAND_UP_DURATION = 1.2
_RECOVER_DURATION = 1.5  # Used only by SkillExecutor, not TransitionManager


def _make_insert(skill: str, duration: float) -> dict:
    """Create a transition-inserted item dict.

    Args:
        skill: Skill name to insert.
        duration: Duration for the inserted skill.

    Returns:
        A dict with 'skill', 'duration', and source='transition_inserted'.
    """
    return {"skill": skill, "duration": duration, "source": "transition_inserted"}


class TransitionManager:
    """Repairs skill sequences to ensure safe, executable transitions.

    Applies 12 transition repair rules from INTERFACES.md §11 in order.
    Tracks the current humanoid pose through the sequence and inserts
    stabilisation / stand-up skills as needed.
    """

    def __init__(self, registry: SkillRegistry):
        """Initialize with a skill registry for skill metadata lookups.

        Args:
            registry: SkillRegistry instance for looking up skill metadata.
        """
        self._registry = registry

    def repair(self, sequence: list[dict]) -> list[dict]:
        """Apply all transition repair rules to a sequence.

        Args:
            sequence: Validated raw sequence items
                [{"skill": str, "duration": float}, ...]

        Returns:
            Repaired sequence items
                [{"skill": str, "duration": float, "source": str}, ...]
            Every output item has: skill, duration, source.
            The input sequence is NOT modified — a new list is returned.
        """
        if not sequence:
            return []

        # ── Pre-pass: Rules 1–3 (mark and clamp) ──────────────────────
        pre_processed: list[dict] = []
        for item in sequence:
            skill_name = item["skill"]
            duration = item["duration"]
            info: SkillInfo = self._registry.get(skill_name)

            new_item = dict(item)  # shallow copy
            new_item["source"] = "agent"  # Rule 1

            min_d, max_d = info.duration_range
            clamped = False

            # Rule 2: Clamp out-of-range durations
            if duration < min_d:
                new_item["duration"] = min_d
                clamped = True
            elif duration > max_d:
                new_item["duration"] = max_d
                clamped = True

            # Rule 3: Mark clamped items
            if clamped:
                new_item["source"] = "duration_clamped"

            pre_processed.append(new_item)

        # ── Iterative pass: Rules 4–12 (pose tracking + risk inserts) ──
        output: list[dict] = []
        current_pose = "standing"  # Humanoid starts standing

        for item in pre_processed:
            skill_name = item["skill"]
            info: SkillInfo = self._registry.get(skill_name)

            # Determine if this is an original item (for risk-insert rules)
            is_original = item["source"] in ("agent", "duration_clamped")

            # ── Rule 8: Before high-risk skill, insert stand_stable ──
            if is_original and info.risk == "high":
                output.append(_make_insert("stand_stable", _STAND_STABLE_DURATION))
                current_pose = "standing"  # stand_stable.end_pose

            # ── Rules 4–7: Pose matching ──
            if info.start_pose == "any":
                # Rule 5: "any" pose — allow starting from any pose
                pass
            elif current_pose == info.start_pose:
                # Rule 4: Pose match — keep as-is
                pass
            elif current_pose == "low_pose" and info.start_pose == "standing":
                # Rule 6: low_pose → standing: insert stand_up
                output.append(_make_insert("stand_up", _STAND_UP_DURATION))
                current_pose = "standing"  # stand_up.end_pose
            else:
                # Rule 7: General pose mismatch — insert stand_stable
                output.append(_make_insert("stand_stable", _STAND_STABLE_DURATION))
                current_pose = "standing"  # stand_stable.end_pose

            # ── Add the item itself ──
            output.append(item)
            current_pose = info.end_pose

            # ── Rule 9: After high-risk skill, insert stand_stable ──
            if is_original and info.risk == "high":
                output.append(_make_insert("stand_stable", _STAND_STABLE_DURATION))
                # After-insert: do NOT update current_pose for the *next*
                # item's pose matching (see INTERFACES.md example and
                # test_squat_to_standing_inserts_stand_up).

            # ── Rule 10: After medium-risk skill, insert stand_stable ──
            if is_original and info.risk == "medium":
                output.append(_make_insert("stand_stable", _STAND_STABLE_DURATION))
                # Same as Rule 9 — after-insert does not affect next
                # item's pose matching.

        # Rule 11 is satisfied by _make_insert always setting source.
        # Rule 12 is satisfied — every item in output has skill, duration, source.

        return output
