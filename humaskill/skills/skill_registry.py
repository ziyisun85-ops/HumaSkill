"""SkillRegistry for loading and querying skill metadata."""

from humaskill.skills.skill_info import SkillInfo
from humaskill.skills.skill_schema import validate_skill
from humaskill.utils.errors import UnknownSkillError
from humaskill.utils.io import load_yaml


class SkillRegistry:
    """Registry of skill metadata loaded from a YAML configuration file.

    Provides lookup by name, existence check, listing all names, and
    filtering by tag.

    Querying an unknown skill via get() raises UnknownSkillError.
    """

    def __init__(self, skills_yaml_path: str):
        """Load and validate skills from a YAML configuration file.

        Args:
            skills_yaml_path: Path to the skills.yaml file.

        Raises:
            InvalidSkillConfigError: If any skill in the YAML fails validation.
            FileNotFoundError: If the YAML file does not exist.
        """
        raw_skills = load_yaml(skills_yaml_path)
        if raw_skills is None:
            raw_skills = []

        self._skills: dict[str, SkillInfo] = {}
        for raw in raw_skills:
            validate_skill(raw)
            skill = SkillInfo(
                name=raw["name"],
                tags=raw["tags"],
                duration_range=(float(raw["duration_range"][0]), float(raw["duration_range"][1])),
                start_pose=raw["start_pose"],
                end_pose=raw["end_pose"],
                risk=raw["risk"],
                description=raw.get("description", ""),
                backend=raw.get("backend", "dummy"),
                policy_id=raw.get("policy_id", None),
                checkpoint=raw.get("checkpoint", None),
                action_type=raw.get("action_type", None),
                obs_adapter=raw.get("obs_adapter", None),
            )
            self._skills[skill.name] = skill

    def get(self, name: str) -> SkillInfo:
        """Return the SkillInfo for the given skill name.

        Args:
            name: Skill name to look up.

        Returns:
            SkillInfo for the requested skill.

        Raises:
            UnknownSkillError: If the skill name is not registered.
        """
        if name not in self._skills:
            raise UnknownSkillError(f"Unknown skill: '{name}'")
        return self._skills[name]

    def has(self, name: str) -> bool:
        """Check if a skill name is registered.

        Args:
            name: Skill name to check.

        Returns:
            True if the skill is registered, False otherwise.
        """
        return name in self._skills

    def all_names(self) -> list[str]:
        """Return a list of all registered skill names.

        Returns:
            List of skill name strings.
        """
        return list(self._skills.keys())

    def skills_with_tag(self, tag: str) -> list[SkillInfo]:
        """Return all SkillInfo instances that have the given tag.

        Args:
            tag: Tag to filter by.

        Returns:
            List of SkillInfo instances with the matching tag.
        """
        return [skill for skill in self._skills.values() if tag in skill.tags]
