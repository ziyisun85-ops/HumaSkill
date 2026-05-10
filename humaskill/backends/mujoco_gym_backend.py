"""Placeholder for future MuJoCo Gym-based skill execution."""

from humaskill.backends.base_backend import BaseBackend, ExecutionResult


class MujocoGymBackend(BaseBackend):
    """Placeholder for future MuJoCo Gym-based skill execution.

    This backend will execute skills inside a MuJoCo physics simulation
    using the Gymnasium API, optionally driven by trained policies.
    Not implemented in the MVP.
    """

    def execute(self, skill_name: str, duration: float) -> ExecutionResult:
        raise NotImplementedError(
            "MujocoGymBackend is a placeholder for future implementation"
        )
