"""Skill schema validation for HumaSkill."""

from humaskill.utils.errors import InvalidSkillConfigError

ALLOWED_RISK_VALUES = {"low", "medium", "high"}


def validate_skill(raw: dict) -> None:
    """Validate a raw skill dictionary loaded from YAML.

    Checks required fields and their types. Raises InvalidSkillConfigError
    for any validation failure with a message naming the skill and reason.

    Args:
        raw: Raw skill dictionary from YAML configuration.

    Raises:
        InvalidSkillConfigError: If validation fails.
    """
    skill_name = raw.get("name", "<unknown>")

    # Required fields
    required_fields = ["name", "tags", "duration_range", "start_pose", "end_pose", "risk"]
    for field in required_fields:
        if field not in raw:
            raise InvalidSkillConfigError(
                f"Skill '{skill_name}': missing required field '{field}'"
            )

    # Validate 'name' is a non-empty string
    if not isinstance(raw["name"], str) or not raw["name"].strip():
        raise InvalidSkillConfigError(
            f"Skill '<unknown>': 'name' must be a non-empty string, got {type(raw['name']).__name__}"
        )
    skill_name = raw["name"]

    # Validate 'tags' is a non-empty list of strings
    tags = raw["tags"]
    if not isinstance(tags, list) or len(tags) == 0:
        raise InvalidSkillConfigError(
            f"Skill '{skill_name}': 'tags' must be a non-empty list, got {type(tags).__name__}"
        )
    for i, tag in enumerate(tags):
        if not isinstance(tag, str):
            raise InvalidSkillConfigError(
                f"Skill '{skill_name}': tag at index {i} must be a string, got {type(tag).__name__}"
            )

    # Validate 'duration_range' is a list/tuple of exactly 2 numbers with min < max
    dr = raw["duration_range"]
    if not isinstance(dr, (list, tuple)) or len(dr) != 2:
        raise InvalidSkillConfigError(
            f"Skill '{skill_name}': 'duration_range' must be a list of exactly 2 numbers, "
            f"got {type(dr).__name__} of length {len(dr) if isinstance(dr, (list, tuple)) else 'N/A'}"
        )
    for i, val in enumerate(dr):
        if not isinstance(val, (int, float)):
            raise InvalidSkillConfigError(
                f"Skill '{skill_name}': duration_range[{i}] must be a number, "
                f"got {type(val).__name__}"
            )
    min_dur, max_dur = float(dr[0]), float(dr[1])
    if min_dur >= max_dur:
        raise InvalidSkillConfigError(
            f"Skill '{skill_name}': duration_range min ({min_dur}) must be less than max ({max_dur})"
        )

    # Validate 'start_pose' is a non-empty string
    if not isinstance(raw["start_pose"], str) or not raw["start_pose"].strip():
        raise InvalidSkillConfigError(
            f"Skill '{skill_name}': 'start_pose' must be a non-empty string, "
            f"got {type(raw['start_pose']).__name__}"
        )

    # Validate 'end_pose' is a non-empty string
    if not isinstance(raw["end_pose"], str) or not raw["end_pose"].strip():
        raise InvalidSkillConfigError(
            f"Skill '{skill_name}': 'end_pose' must be a non-empty string, "
            f"got {type(raw['end_pose']).__name__}"
        )

    # Validate 'risk' is one of allowed values
    risk = raw["risk"]
    if not isinstance(risk, str) or risk not in ALLOWED_RISK_VALUES:
        raise InvalidSkillConfigError(
            f"Skill '{skill_name}': 'risk' must be one of {sorted(ALLOWED_RISK_VALUES)}, "
            f"got '{risk}'"
        )
