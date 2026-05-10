"""Placeholder for future policy observation adaptation."""

from humaskill.policies.base_policy import BaseSkillPolicy


class PolicyAdapter:
    """Placeholder for future observation conversion.

    Converts environment observations into the format expected by
    a specific pre-trained skill policy. Not implemented in the MVP.
    """

    def build_policy_obs(self, skill_name: str, env_obs: dict) -> dict:
        """Convert environment observation to policy observation.

        Args:
            skill_name: Skill being executed.
            env_obs: Raw environment observation.

        Returns:
            Observation dict formatted for the skill policy.
        """
        raise NotImplementedError(
            "PolicyAdapter is a placeholder for future implementation"
        )
