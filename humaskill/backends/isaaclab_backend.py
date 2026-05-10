"""Placeholder for future Isaac Lab-based skill execution."""

from humaskill.backends.base_backend import BaseBackend, ExecutionResult


class IsaacLabBackend(BaseBackend):
    """Placeholder for future Isaac Lab-based skill execution.

    This backend will execute skills inside NVIDIA Isaac Lab (Isaac Sim)
    for high-fidelity humanoid simulation with Omniverse rendering.
    Not implemented in the MVP.
    """

    def execute(self, skill_name: str, duration: float) -> ExecutionResult:
        raise NotImplementedError(
            "IsaacLabBackend is a placeholder for future implementation"
        )
