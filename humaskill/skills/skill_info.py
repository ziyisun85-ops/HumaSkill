"""SkillInfo dataclass for HumaSkill."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillInfo:
    """Immutable skill metadata container.

    Fields match the binding contract in INTERFACES.md §1 exactly.
    """

    name: str
    tags: list[str]
    duration_range: tuple[float, float]
    start_pose: str
    end_pose: str
    risk: str
    description: str = ""
    backend: str = "dummy"
    policy_id: str | None = None
    checkpoint: str | None = None
    action_type: str | None = None
    obs_adapter: str | None = None
