from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Optional

import numpy as np

from middle_architecture.matcher import MotionMatcher
from middle_architecture.reference_ops import reanchor_reference_frames, slice_motion_to_reference_frames
from middle_architecture.robot_state import ReferenceSegment
from middle_architecture.transition_builder import TransitionBuilder


@dataclass
class ExecutionResult:
    segment_id: str
    segment_type: str
    skill_name: Optional[str]
    success: bool
    final_state: Optional[Any]
    num_frames: int
    source_motion_path: Optional[str] = None
    log_path: Optional[str] = None
    video_path: Optional[str] = None
    failed_reason: Optional[str] = None


class HarnessOrchestrator:
    def __init__(self, runner, skill_registry, transition_registry, motion_adapter, config):
        self.runner = runner
        self.skill_registry = skill_registry
        self.transition_registry = transition_registry
        self.motion_adapter = motion_adapter
        self.config = config or {}
        self.matcher = MotionMatcher()
        self.transition_builder = TransitionBuilder(
            motion_source=skill_registry,
            motion_adapter=motion_adapter,
        )
        runtime = self.config.get("runtime", {})
        self.output_root = Path(runtime.get("output_root", "outputs"))
        self.stop_on_failure = bool(runtime.get("stop_on_failure", True))
        self.reference_contract = self.config.get("reference_contract", {})

    def execute(self, skill_plan) -> list:
        self.runner.initialize()
        task_output_dir = self.output_root / skill_plan.task_id
        task_output_dir.mkdir(parents=True, exist_ok=True)

        results = []
        state = self.runner.get_robot_state()
        previous_skill = None
        transition_count = 0

        for index, item in enumerate(skill_plan.sequence, start=1):
            skill_spec = self.skill_registry.get(item.skill)
            motion = self.motion_adapter.load(skill_spec.motion_file)
            match = self.matcher.select(
                robot_state=state,
                skill_spec=skill_spec,
                motion=motion,
                duration=item.duration,
            )
            skill_frames = slice_motion_to_reference_frames(
                motion,
                match.start_frame,
                match.end_frame,
            )
            if self.reference_contract.get("reanchor_skill_clip") is True:
                skill_frames = reanchor_reference_frames(
                    skill_frames,
                    state,
                    {
                        "root_reference_mode": self.reference_contract.get(
                            "root_reference_mode", "root_relative"
                        ),
                        "reanchor_yaw_only": self.reference_contract.get(
                            "reanchor_yaw_only", True
                        ),
                    },
                )

            if previous_skill is not None:
                transition_count += 1
                transition_spec = self.transition_registry.get(previous_skill, item.skill)
                tag = f"transition_{transition_count:03d}_{previous_skill}_to_{item.skill}"

                if transition_spec.mode == "bridge":
                    body_seg = self.transition_builder.build_bridge_body(
                        transition_spec, state, skill_spec
                    )
                    body_seg.segment_id = f"{tag}_body"
                    body_result = self._execute_segment(body_seg, task_output_dir)
                    results.append(body_result)
                    state = body_result.final_state
                    if not body_result.success and self.stop_on_failure:
                        self._write_summary(skill_plan.task_id, results, task_output_dir)
                        return results

                    post_seg = self.transition_builder.build_bridge_post(
                        transition_spec, state, skill_spec
                    )
                    if post_seg is not None:
                        post_seg.segment_id = f"{tag}_post"
                        post_result = self._execute_segment(post_seg, task_output_dir)
                        results.append(post_result)
                        state = post_result.final_state
                        if not post_result.success and self.stop_on_failure:
                            self._write_summary(skill_plan.task_id, results, task_output_dir)
                            return results
                else:
                    transition_segment = self.transition_builder.build_transition(
                        transition_spec, state, skill_spec,
                    )
                    transition_segment.segment_id = tag
                    result = self._execute_segment(transition_segment, task_output_dir)
                    results.append(result)
                    state = result.final_state
                    if not result.success and self.stop_on_failure:
                        self._write_summary(skill_plan.task_id, results, task_output_dir)
                        return results

            skill_segment = ReferenceSegment(
                segment_id=f"skill_{index:03d}_{item.skill}",
                segment_type="skill",
                skill_name=item.skill,
                reference_frames=skill_frames,
                source_motion_path=skill_spec.motion_file,
                start_frame=match.start_frame,
                end_frame=match.end_frame,
                target_duration=item.duration,
                reason=match.reason,
            )
            result = self._execute_segment(skill_segment, task_output_dir)
            results.append(result)
            state = result.final_state
            if not result.success and self.stop_on_failure:
                self._write_summary(skill_plan.task_id, results, task_output_dir)
                return results
            previous_skill = item.skill

        self._write_summary(skill_plan.task_id, results, task_output_dir)
        return results

    def _execute_segment(self, segment: ReferenceSegment, task_output_dir: Path) -> ExecutionResult:
        segment_dir = task_output_dir / segment.segment_id
        segment_dir.mkdir(parents=True, exist_ok=True)
        track_result = self.runner.track(segment.reference_frames)
        final_state = self.runner.get_robot_state()
        self._write_robot_state(final_state, segment_dir / "robot_state_final.npz")

        result_json = segment_dir / "result.json"
        payload = {
            "segment_id": segment.segment_id,
            "segment_type": segment.segment_type,
            "skill_name": segment.skill_name,
            "success": track_result.success,
            "num_frames": track_result.num_frames,
            "source_motion_path": segment.source_motion_path,
            "start_frame": segment.start_frame,
            "end_frame": segment.end_frame,
            "target_duration": segment.target_duration,
            "transition_type": segment.transition_type,
            "from_skill": segment.from_skill,
            "to_skill": segment.to_skill,
            "failed_reason": track_result.failed_reason,
            "final_root_pos": final_state.root_pos.tolist(),
        }
        result_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        return ExecutionResult(
            segment_id=segment.segment_id,
            segment_type=segment.segment_type,
            skill_name=segment.skill_name,
            success=track_result.success,
            final_state=final_state,
            num_frames=track_result.num_frames,
            source_motion_path=segment.source_motion_path,
            log_path=str(result_json),
            video_path=track_result.video_path,
            failed_reason=track_result.failed_reason,
        )

    def _write_summary(self, task_id: str, results: list, task_output_dir: Path):
        log = []
        for result in results:
            log.append(
                {
                    "segment_id": result.segment_id,
                    "segment_type": result.segment_type,
                    "skill_name": result.skill_name,
                    "success": result.success,
                    "num_frames": result.num_frames,
                    "source_motion_path": result.source_motion_path,
                    "log_path": result.log_path,
                    "failed_reason": result.failed_reason,
                }
            )
        (task_output_dir / "execution_log.json").write_text(
            json.dumps(log, indent=2), encoding="utf-8"
        )
        summary = {
            "task_id": task_id,
            "success": all(item.success for item in results),
            "num_segments": len(results),
            "failed_segments": [
                item.segment_id for item in results if not item.success
            ],
        }
        (task_output_dir / "run_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )

    def _write_robot_state(self, state, path: Path):
        np.savez(
            path,
            root_pos=state.root_pos,
            root_quat=state.root_quat,
            dof_pos=state.dof_pos,
            root_lin_vel=state.root_lin_vel,
            root_ang_vel=state.root_ang_vel,
            dof_vel=state.dof_vel,
        )
