"""BaseComposer abstract base class for HumaSkill.

Defines the composer interface per INTERFACES.md §7.
"""

from abc import ABC, abstractmethod


class BaseComposer(ABC):
    """Abstract base class for skill sequence composers.

    A composer converts a natural language instruction into a raw skill
    sequence — a list of dicts with 'skill' and 'duration' keys.
    """

    @abstractmethod
    def compose(self, text: str, duration: float, seed: int | None = None) -> list[dict]:
        """Convert a language instruction into a raw skill sequence.

        Args:
            text: Natural language instruction (Chinese text).
            duration: Target total duration in seconds.
            seed: Optional random seed for reproducibility.

        Returns:
            A list of raw sequence items:
                [{"skill": str, "duration": float}, ...]
        """
        raise NotImplementedError
