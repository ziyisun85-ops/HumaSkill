from abc import ABC, abstractmethod
from typing import Any

from middle_architecture.skill_motion import SkillMotion


class SourceAdapter(ABC):
    @abstractmethod
    def convert(self, *args: Any, **kwargs: Any) -> SkillMotion:
        """Convert a source asset into a SkillMotion."""
        raise NotImplementedError
