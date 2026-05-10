"""Base skill policy interface for HumaSkill.

Follows INTERFACES.md §8 strictly.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseSkillPolicy(ABC):
    """Abstract base for pre-trained skill policies.

    Pre-trained skill policies handle low-level control for individual skills.
    HumaSkill handles high-level composition, transition repair, and recovery.
    """

    @abstractmethod
    def reset(self, skill_name: str, skill_param: dict | None = None) -> None:
        """Reset internal policy state before executing a skill.

        Args:
            skill_name: Name of the skill to execute.
            skill_param: Optional skill-specific parameters.
        """
        raise NotImplementedError

    @abstractmethod
    def act(self, obs: dict[str, Any]) -> Any:
        """Return low-level action from policy observation.

        Args:
            obs: Environment observation dictionary.

        Returns:
            Action in the format expected by the backend environment.
        """
        raise NotImplementedError
