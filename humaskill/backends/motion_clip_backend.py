"""Placeholder for future motion-clip-based skill execution."""

from humaskill.backends.base_backend import BaseBackend, ExecutionResult


class MotionClipBackend(BaseBackend):
    """Placeholder for future motion-clip-based skill execution.

    This backend will execute skills by playing back pre-recorded
    motion capture clips. Not implemented in the MVP.
    """

    def execute(self, skill_name: str, duration: float) -> ExecutionResult:
        raise NotImplementedError(
            "MotionClipBackend is a placeholder for future implementation"
        )
