"""LLMComposer — placeholder for future LLM-based skill composition."""

from humaskill.composer.base_composer import BaseComposer


class LLMComposer(BaseComposer):
    """Placeholder for future LLM-based skill composition.

    This class reserves the integration point for an LLM that can
    directly reason about skill sequences from natural language.
    It is intentionally not implemented in the MVP.
    """

    def compose(
        self, text: str, duration: float, seed: int | None = None
    ) -> list[dict]:
        """Not implemented — placeholder for future use.

        Args:
            text: Natural language instruction.
            duration: Target total duration in seconds.
            seed: Optional random seed for reproducibility.

        Raises:
            NotImplementedError: Always, as this is a placeholder.
        """
        raise NotImplementedError(
            "LLMComposer is a placeholder for future implementation"
        )
