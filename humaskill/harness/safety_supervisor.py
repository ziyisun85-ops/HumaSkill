"""SafetySupervisor — monitors safety during skill execution.

In the MVP this is a lightweight monitoring class that tracks execution
state and can flag safety concerns.  Full safety checks (joint limits,
velocity limits, collision detection) are reserved for future backends
(MuJoCo, Isaac Lab).
"""

from typing import Any


class SafetySupervisor:
    """Monitors safety during skill execution.

    Provides hook points for pre- and post-execution safety checks.
    In the MVP these always return True (safe), but the interface
    is designed to accept ExecutionResult objects from the backend
    for future integration.
    """

    def __init__(self):
        """Initialize the safety supervisor.

        Resets internal state for a fresh execution run.
        """
        self._execution_count = 0
        self._failure_count = 0

    def check_pre_execution(self, skill_name: str) -> bool:
        """Check safety before executing a skill.

        In MVP, always returns True (safe to proceed).

        Args:
            skill_name: Name of the skill about to be executed.

        Returns:
            True if safe to proceed, False if a safety stop is needed.
        """
        self._execution_count += 1
        return True

    def check_post_execution(self, skill_name: str, result: Any) -> bool:
        """Check safety after executing a skill.

        In MVP, returns True unless the result itself indicates failure
        (i.e. result.status == "failed").  The result is expected to be
        an ExecutionResult from the backend, but duck-typing is used so
        that any object with a ``status`` attribute works.

        Args:
            skill_name: Name of the skill that was executed.
            result: ExecutionResult from the backend (duck-typed).

        Returns:
            True if safe to continue, False if recovery is needed.
        """
        try:
            if result.status == "failed":
                self._failure_count += 1
                return False
        except AttributeError:
            # result doesn't have a status field — assume safe
            pass
        return True

    def reset(self) -> None:
        """Reset safety state for a new execution run."""
        self._execution_count = 0
        self._failure_count = 0
