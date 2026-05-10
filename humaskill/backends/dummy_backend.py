"""Dummy dance backend for MVP skill execution with configurable failure rate.

Seed-based random ensures reproducibility. Some skills (turn_left, turn_right,
squat) have higher natural failure rates to simulate challenging motions.
"""

import random

from humaskill.backends.base_backend import BaseBackend, ExecutionResult


# Skills with inherently higher failure rates (imitate real-world difficulty).
_HIGH_FAIL_SKILLS: set[str] = {"turn_left", "turn_right", "squat"}
# Multiplier applied to fail_prob for high-fail skills.
_HIGH_FAIL_MULTIPLIER: float = 2.5


class DummyDanceBackend(BaseBackend):
    """MVP dummy backend that simulates skill execution with configurable failure rate.

    Uses a seeded random number generator so that fail_prob + seed produce
    reproducible results. When fail_prob is 0.0, all executions succeed.
    When fail_prob is 1.0, all executions fail.

    Some skills (turn_left, turn_right, squat) are considered inherently
    harder and have their effective fail_prob multiplied by 2.5, capped at 1.0.
    """

    def __init__(self, fail_prob: float = 0.0, seed: int | None = None):
        """Initialize the dummy backend.

        Args:
            fail_prob: Probability of execution failure (0.0 to 1.0).
            seed: Random seed for reproducible failure patterns.

        Raises:
            ValueError: If fail_prob is not in [0.0, 1.0].
        """
        if not 0.0 <= fail_prob <= 1.0:
            raise ValueError(
                f"fail_prob must be in [0.0, 1.0], got {fail_prob}"
            )
        self._fail_prob = fail_prob
        self._seed = seed
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, skill_name: str, duration: float) -> ExecutionResult:
        """Execute a skill and return a structured ExecutionResult.

        Args:
            skill_name: Name of the skill to execute.
            duration: Planned execution duration in seconds.

        Returns:
            ExecutionResult indicating success or failure.

        Raises:
            ValueError: If skill_name is empty or duration <= 0.
        """
        if not skill_name:
            raise ValueError("skill_name must not be empty")
        if duration <= 0:
            raise ValueError(f"duration must be > 0, got {duration}")

        effective_fp = self._effective_fail_prob(skill_name)
        failed = self._rng.random() < effective_fp

        if failed:
            return ExecutionResult(
                status="failed",
                skill=skill_name,
                duration=duration,
                steps=0,
                failure_reason="Simulated dummy backend failure",
                info={"backend": "dummy", "simulated": True},
            )

        steps = max(1, int(duration * 10))
        return ExecutionResult(
            status="success",
            skill=skill_name,
            duration=duration,
            steps=steps,
            info={"backend": "dummy", "simulated": True},
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _effective_fail_prob(self, skill_name: str) -> float:
        """Return the effective fail probability for a skill.

        High-fail skills (turn_left, turn_right, squat) get a multiplier
        applied, capped at 1.0.
        """
        if skill_name in _HIGH_FAIL_SKILLS:
            return min(1.0, self._fail_prob * _HIGH_FAIL_MULTIPLIER)
        return self._fail_prob
