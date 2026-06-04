from dataclasses import dataclass
from typing import Optional

import yaml


@dataclass
class SkillPlanItem:
    skill: str
    duration: Optional[float] = None


@dataclass
class SkillPlan:
    task_id: str
    sequence: list


def parse_task_sequence(yaml_path: str) -> SkillPlan:
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Task sequence YAML must be a mapping: {yaml_path}")
    task_id = data.get("task_id")
    if not task_id:
        raise ValueError("Task sequence requires task_id")
    raw_sequence = data.get("sequence")
    if not isinstance(raw_sequence, list) or not raw_sequence:
        raise ValueError("Task sequence requires a non-empty sequence list")

    sequence = []
    for index, item in enumerate(raw_sequence):
        if not isinstance(item, dict):
            raise ValueError(f"sequence[{index}] must be a mapping")
        skill = item.get("skill")
        if not skill:
            raise ValueError(f"sequence[{index}] requires skill")
        duration = item.get("duration")
        if duration is not None:
            duration = float(duration)
        sequence.append(SkillPlanItem(skill=str(skill), duration=duration))

    return SkillPlan(task_id=str(task_id), sequence=sequence)
