"""Placeholder for future GR00T-based skill execution."""

from humaskill.backends.base_backend import BaseBackend, ExecutionResult


class GrootBackend(BaseBackend):
    """Placeholder for future GR00T-based skill execution.

    This backend will execute skills using NVIDIA GR00T (Generalist Robot
    00 Technology) for humanoid foundation-model-based control.
    Not implemented in the MVP.
    """

    def execute(self, skill_name: str, duration: float) -> ExecutionResult:
        raise NotImplementedError(
            "GrootBackend is a placeholder for future implementation"
        )
