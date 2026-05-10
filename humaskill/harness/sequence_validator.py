"""SequenceValidator for raw skill sequence validation."""

from humaskill.skills.skill_registry import SkillRegistry
from humaskill.utils.errors import InvalidSequenceError


class SequenceValidator:
    """Validates raw sequence items from composer output.

    Checks that every item has the required fields, skills exist in the
    registry, and durations are positive.  Raises InvalidSequenceError
    with a descriptive message on the first invalid item encountered.
    """

    def __init__(self, registry: SkillRegistry):
        """Initialize with a skill registry for skill existence checks.

        Args:
            registry: SkillRegistry instance for validating skill names.
        """
        self._registry = registry

    def validate(self, raw_sequence: list[dict]) -> None:
        """Validate every item in a raw sequence.

        Each item must:
        - Be a dict with keys 'skill' and 'duration'
        - 'skill' must be a non-empty string existing in the registry
        - 'duration' must be a positive number (int or float, > 0)

        The sequence itself must not be empty.

        Args:
            raw_sequence: List of raw sequence items from the composer.

        Raises:
            InvalidSequenceError: If any item is invalid.  The message
                includes the offending item index and the reason.
        """
        if not raw_sequence:
            raise InvalidSequenceError("Sequence must not be empty")

        for i, item in enumerate(raw_sequence):
            # Must be a dict
            if not isinstance(item, dict):
                raise InvalidSequenceError(
                    f"Item {i} is not a dict: {type(item).__name__}"
                )

            # Must have 'skill' key
            if "skill" not in item:
                raise InvalidSequenceError(
                    f"Item {i} is missing required key 'skill'"
                )

            # Must have 'duration' key
            if "duration" not in item:
                raise InvalidSequenceError(
                    f"Item {i} is missing required key 'duration'"
                )

            skill_name = item["skill"]
            duration = item["duration"]

            # 'skill' must be a non-empty string
            if not isinstance(skill_name, str) or skill_name == "":
                raise InvalidSequenceError(
                    f"Item {i}: 'skill' must be a non-empty string, "
                    f"got {type(skill_name).__name__} = {skill_name!r}"
                )

            # Skill must exist in registry
            if not self._registry.has(skill_name):
                raise InvalidSequenceError(
                    f"Item {i}: unknown skill '{skill_name}'"
                )

            # 'duration' must be a positive number
            if not isinstance(duration, (int, float)):
                raise InvalidSequenceError(
                    f"Item {i}: 'duration' must be a number, "
                    f"got {type(duration).__name__} = {duration!r}"
                )
            if duration <= 0:
                raise InvalidSequenceError(
                    f"Item {i}: 'duration' must be positive, got {duration}"
                )
