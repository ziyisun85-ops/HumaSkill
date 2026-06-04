from dataclasses import dataclass
from typing import Optional

import yaml

from task_plan.skill_plan import SkillPlan


@dataclass
class SkillSpec:
    name: str
    motion_file: str
    default_start_frame: int = 0
    default_end_frame: Optional[int] = None
    fps: float = 30.0
    description: str = ""


class SkillRegistry:
    def __init__(self, skills):
        self.skills = dict(skills)

    @staticmethod
    def from_yaml(yaml_path: str) -> "SkillRegistry":
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict) or not isinstance(data.get("skills"), dict):
            raise ValueError(f"Skill registry YAML must contain a skills mapping: {yaml_path}")

        skills = {}
        for name, raw in data["skills"].items():
            if not isinstance(raw, dict):
                raise ValueError(f"Skill {name} spec must be a mapping")
            skills[name] = SkillSpec(
                name=str(name),
                motion_file=str(raw["motion_file"]),
                default_start_frame=int(raw.get("default_start_frame", 0)),
                default_end_frame=raw.get("default_end_frame"),
                fps=float(raw.get("fps", 30.0)),
                description=str(raw.get("description", "")),
            )
            if skills[name].default_end_frame is not None:
                skills[name].default_end_frame = int(skills[name].default_end_frame)
        return SkillRegistry(skills)

    def has(self, skill_name: str) -> bool:
        return skill_name in self.skills

    def get(self, skill_name: str) -> SkillSpec:
        if skill_name not in self.skills:
            raise KeyError(f"Unknown skill: {skill_name}")
        return self.skills[skill_name]

    def validate(self, skill_plan: SkillPlan) -> None:
        for item in skill_plan.sequence:
            self.get(item.skill)
