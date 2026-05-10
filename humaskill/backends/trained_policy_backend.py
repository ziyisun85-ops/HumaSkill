"""Placeholder for future trained-policy-based skill execution."""

from humaskill.backends.base_backend import BaseBackend, ExecutionResult


class TrainedPolicyBackend(BaseBackend):
    """Placeholder for future trained-policy-based skill execution.

    This backend will execute skills by running pre-trained skill policies
    (loaded from checkpoints) inside a simulation environment.
    Not implemented in the MVP.
    """

    def execute(self, skill_name: str, duration: float) -> ExecutionResult:
        raise NotImplementedError(
            "TrainedPolicyBackend is a placeholder for future implementation"
        )
