"""Base backend interface and ExecutionResult for HumaSkill.

Follows INTERFACES.md §4 and §6 strictly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionResult:
    """Structured result returned by every backend after executing a skill.

    Allowed status values: ONLY "success" or "failed".
    MVP (DummyBackend) fills: status, skill, duration, steps, failure_reason, info.
    Future backends add: reward, final_obs.
    """

    status: str
    skill: str
    duration: float
    steps: int = 0
    reward: float | None = None
    final_obs: dict[str, Any] | None = None
    info: dict[str, Any] = field(default_factory=dict)
    failure_reason: str | None = None


class BaseBackend(ABC):
    """Abstract base class for all skill execution backends.

    Every backend MUST return ExecutionResult.
    ExecutionResult.status MUST be "success" or "failed".
    Backends MUST NOT return raw strings.
    """

    @abstractmethod
    def execute(self, skill_name: str, duration: float) -> ExecutionResult:
        """Execute a skill and return a structured execution result.

        Args:
            skill_name: Name of the skill to execute.
            duration: Planned execution duration in seconds.

        Returns:
            ExecutionResult with status, skill name, duration, and backend data.
        """
        raise NotImplementedError
