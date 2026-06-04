import argparse
from pathlib import Path
import sys

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from low_level_execution.gmt_tracking_runner import GMTTrackingRunner
from middle_architecture.gmt_motion_adapter import GmtMotionAdapter
from middle_architecture.harness_orchestrator import HarnessOrchestrator
from middle_architecture.transition_registry import TransitionRegistry
from task_plan.skill_plan import parse_task_sequence
from task_plan.skill_registry import SkillRegistry


def load_harness_config(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/harness.yaml")
    parser.add_argument("--sequence", default=None)
    parser.add_argument("--skills", default="configs/skills.yaml")
    parser.add_argument("--transitions", default="configs/transitions.yaml")
    args = parser.parse_args()

    config = load_harness_config(args.config)
    sequence_path = args.sequence or config["sequence"]["default_task"]
    skill_plan = parse_task_sequence(sequence_path)
    skill_registry = SkillRegistry.from_yaml(args.skills)
    skill_registry.validate(skill_plan)
    transition_registry = TransitionRegistry.from_yaml(args.transitions)

    motion_adapter = GmtMotionAdapter(config["motion_assets"]["root"])
    runner = GMTTrackingRunner(
        gmt_root=config["gmt"]["root"],
        robot=config["gmt"].get("robot", "g1"),
        device=config["gmt"].get("device", "auto"),
        fall_config=config.get("fall_detection"),
    )
    orchestrator = HarnessOrchestrator(
        runner=runner,
        skill_registry=skill_registry,
        transition_registry=transition_registry,
        motion_adapter=motion_adapter,
        config=config,
    )
    results = orchestrator.execute(skill_plan)

    for result in results:
        print(
            result.segment_id,
            "success=",
            result.success,
            "failed_reason=",
            result.failed_reason,
        )
    if not all(result.success for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
