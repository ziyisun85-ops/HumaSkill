"""Placeholder for future checkpoint loading."""

from humaskill.policies.base_policy import BaseSkillPolicy


class CheckpointLoader:
    """Placeholder for future checkpoint loading.

    Loads pre-trained skill policies from checkpoint files
    ('.pt', '.pth', '.pkl', '.npz'). Not implemented in the MVP.
    """

    def load(self, checkpoint_path: str) -> BaseSkillPolicy:
        """Load a pretrained skill policy from checkpoint.

        Args:
            checkpoint_path: Path to the checkpoint file.

        Returns:
            Loaded BaseSkillPolicy instance.
        """
        raise NotImplementedError(
            "CheckpointLoader is a placeholder for future implementation"
        )
