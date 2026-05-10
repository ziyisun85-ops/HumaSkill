"""Tests for SkillRegistry covering all 8 test cases from TEST_PLAN.md."""

import sys
from pathlib import Path

import pytest

# Ensure HumaSkill is importable
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from humaskill.skills.skill_info import SkillInfo
from humaskill.skills.skill_registry import SkillRegistry
from humaskill.utils.errors import UnknownSkillError

SKILLS_YAML_PATH = str(project_root / "configs" / "skills.yaml")


@pytest.fixture
def registry():
    """Create a SkillRegistry from the project's skills.yaml."""
    return SkillRegistry(SKILLS_YAML_PATH)


class TestSkillRegistry:
    """Test suite for SkillRegistry — 8 test cases from TEST_PLAN.md."""

    def test_load_skills_yaml(self, registry):
        """TestCase 1: skills.yaml loads successfully, returns non-empty registry."""
        assert registry is not None
        names = registry.all_names()
        assert len(names) > 0
        # Verify it contains the known skills
        assert "stand_ready" in names

    def test_stand_ready_exists(self, registry):
        """TestCase 2: stand_ready is present in the registry."""
        skill = registry.get("stand_ready")
        assert skill.name == "stand_ready"
        assert isinstance(skill.tags, list)
        assert "basic" in skill.tags

    def test_recover_exists(self, registry):
        """TestCase 3: recover is present in the registry."""
        skill = registry.get("recover")
        assert skill.name == "recover"
        assert skill.risk in ("low", "medium", "high")

    def test_all_names_returns_list(self, registry):
        """TestCase 4: all_names() returns a non-empty list of strings."""
        names = registry.all_names()
        assert isinstance(names, list)
        assert len(names) > 0
        for name in names:
            assert isinstance(name, str)

    def test_unknown_skill_raises_error(self, registry):
        """TestCase 5: Querying a non-existent skill raises UnknownSkillError."""
        with pytest.raises(UnknownSkillError) as exc_info:
            registry.get("nonexistent_skill_xyz")
        assert "nonexistent_skill_xyz" in str(exc_info.value)

    def test_extended_fields_loaded(self, registry):
        """TestCase 6: backend, policy_id, checkpoint, action_type, obs_adapter
        fields are loaded from YAML."""
        skill = registry.get("stand_ready")
        # All extended fields should be present on the SkillInfo dataclass
        assert hasattr(skill, "backend")
        assert hasattr(skill, "policy_id")
        assert hasattr(skill, "checkpoint")
        assert hasattr(skill, "action_type")
        assert hasattr(skill, "obs_adapter")
        # backend defaults to "dummy"
        assert skill.backend == "dummy"
        # Optional fields can be None for basic skills
        assert skill.policy_id is None
        assert skill.checkpoint is None
        assert skill.action_type is None
        assert skill.obs_adapter is None

    def test_skills_with_tag(self, registry):
        """TestCase 7: skills_with_tag('dance') returns only skills tagged 'dance'."""
        dance_skills = registry.skills_with_tag("dance")
        assert isinstance(dance_skills, list)
        assert len(dance_skills) > 0
        for skill in dance_skills:
            assert "dance" in skill.tags

    def test_skill_info_dataclass(self):
        """TestCase 8: SkillInfo is a frozen dataclass with all required fields."""
        # Verify frozen: attempting to set an attribute should raise FrozenInstanceError
        skill = SkillInfo(
            name="test_skill",
            tags=["test"],
            duration_range=(1.0, 3.0),
            start_pose="standing",
            end_pose="standing",
            risk="low",
        )
        with pytest.raises(Exception):
            skill.name = "changed"  # frozen dataclass prevents mutation

        # Verify all fields are present
        assert hasattr(skill, "name")
        assert hasattr(skill, "tags")
        assert hasattr(skill, "duration_range")
        assert hasattr(skill, "start_pose")
        assert hasattr(skill, "end_pose")
        assert hasattr(skill, "risk")
        assert hasattr(skill, "description")
        assert hasattr(skill, "backend")
        assert hasattr(skill, "policy_id")
        assert hasattr(skill, "checkpoint")
        assert hasattr(skill, "action_type")
        assert hasattr(skill, "obs_adapter")

        # Verify defaults
        assert skill.description == ""
        assert skill.backend == "dummy"
        assert skill.policy_id is None
        assert skill.checkpoint is None
        assert skill.action_type is None
        assert skill.obs_adapter is None
