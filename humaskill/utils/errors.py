"""Custom exceptions for HumaSkill."""


class HumaSkillError(Exception):
    """Base exception for HumaSkill."""
    pass


class UnknownSkillError(HumaSkillError):
    """Skill not found in registry."""
    pass


class InvalidSkillConfigError(HumaSkillError):
    """Skill configuration validation failed."""
    pass


class InvalidSequenceError(HumaSkillError):
    """Sequence validation failed."""
    pass


class BackendExecutionError(HumaSkillError):
    """Backend execution failed."""
    pass


class PolicyLoadError(HumaSkillError):
    """Policy checkpoint loading failed."""
    pass
