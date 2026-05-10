"""Placeholder for future TextOp-based skill execution."""

from humaskill.backends.base_backend import BaseBackend, ExecutionResult


class TextOpBackend(BaseBackend):
    """Placeholder for future TextOp-based skill execution.

    This backend will execute skills by generating motion trajectories
    from text descriptions using a TextOp-class model (text-to-motion).
    Not implemented in the MVP.
    """

    def execute(self, skill_name: str, duration: float) -> ExecutionResult:
        raise NotImplementedError(
            "TextOpBackend is a placeholder for future implementation"
        )
