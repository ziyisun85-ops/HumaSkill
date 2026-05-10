"""PolicyRegistry for mapping skill names to policy instances.

Follows INTERFACES.md §8 strictly.
"""

from humaskill.policies.base_policy import BaseSkillPolicy


class PolicyRegistry:
    """Registry that maps skill names to BaseSkillPolicy instances.

    Methods:
        register(skill_name, policy) -> None
        get(skill_name) -> BaseSkillPolicy
        has(skill_name) -> bool
        all_names() -> list[str]
    """

    def __init__(self):
        self._policies: dict[str, BaseSkillPolicy] = {}

    def register(self, skill_name: str, policy: BaseSkillPolicy) -> None:
        """Register a skill policy for a given skill name.

        Args:
            skill_name: Skill name to register the policy for.
            policy: BaseSkillPolicy instance.

        Raises:
            ValueError: If skill_name is already registered.
            TypeError: If policy is not a BaseSkillPolicy instance.
        """
        if not isinstance(policy, BaseSkillPolicy):
            raise TypeError(
                f"policy must be a BaseSkillPolicy instance, got {type(policy).__name__}"
            )
        if skill_name in self._policies:
            raise ValueError(
                f"Skill '{skill_name}' is already registered with a policy"
            )
        self._policies[skill_name] = policy

    def get(self, skill_name: str) -> BaseSkillPolicy:
        """Retrieve the policy for a given skill name.

        Args:
            skill_name: Skill name to look up.

        Returns:
            BaseSkillPolicy instance.

        Raises:
            KeyError: If skill_name is not registered.
        """
        if skill_name not in self._policies:
            raise KeyError(
                f"No policy registered for skill '{skill_name}'"
            )
        return self._policies[skill_name]

    def has(self, skill_name: str) -> bool:
        """Check if a skill name has a registered policy.

        Args:
            skill_name: Skill name to check.

        Returns:
            True if registered, False otherwise.
        """
        return skill_name in self._policies

    def all_names(self) -> list[str]:
        """Return all registered skill names.

        Returns:
            List of skill name strings.
        """
        return list(self._policies.keys())
