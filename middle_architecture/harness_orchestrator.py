import dataclasses
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Optional

import numpy as np

from middle_architecture.evaluation import SegmentMetrics
from middle_architecture.matcher import MotionMatcher
from middle_architecture.reference_ops import reanchor_reference_frames, slice_motion_to_reference_frames
from middle_architecture.robot_state import MatchConfig, ReferenceSegment, TransitionMetrics
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
    metrics: Optional[SegmentMetrics] = None


class HarnessOrchestrator:
    def __init__(self, runner, skill_registry, transition_registry, motion_adapter, config):
        self.runner = runner
        self.skill_registry = skill_registry
        self.transition_registry = transition_registry
        self.motion_adapter = motion_adapter
        self.config = config or {}
        m = self.config.get("matching", {})
        match_config = MatchConfig(
            mode=m.get("mode", "static"),
            search_window=int(m.get("search_window", 60)),
            score_weights=m.get("score_weights"),
        )
        self.matcher = MotionMatcher(match_config=match_config)
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

            if previous_skill is not None:
                transition_count += 1
                transition_spec = self.transition_registry.get(previous_skill, item.skill)
                tag = f"transition_{transition_count:03d}_{previous_skill}_to_{item.skill}"

                if transition_spec.mode == "bridge":
                    body_seg = self.transition_builder.build_bridge_body(
                        transition_spec, state
                    )
                    body_seg.segment_id = f"{tag}_body"
                    body_result = self._execute_segment(body_seg, task_output_dir)
                    results.append(body_result)
                    state = body_result.final_state
                    if not body_result.success and self.stop_on_failure:
                        self._write_summary(skill_plan.task_id, results, task_output_dir)
                        return results

                    post_seg = self.transition_builder.build_bridge_post(
                        transition_spec, state, skill_spec, target_frame_idx=match.start_frame
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
                        transition_spec, state, skill_spec, target_frame_idx=match.start_frame,
                    )
                    transition_segment.segment_id = tag
                    result = self._execute_segment(transition_segment, task_output_dir)
                    results.append(result)
                    state = result.final_state
                    if not result.success and self.stop_on_failure:
                        self._write_summary(skill_plan.task_id, results, task_output_dir)
                        return results

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
        seg_metrics = track_result.metrics
        trans_metrics_raw = (segment.metadata or {}).get("transition_metrics")
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
            "metrics": dataclasses.asdict(seg_metrics) if seg_metrics is not None else None,
            "transition_metrics": dataclasses.asdict(trans_metrics_raw)
            if isinstance(trans_metrics_raw, TransitionMetrics)
            else trans_metrics_raw,
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
            metrics=seg_metrics,
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
        self._write_metrics_summary(task_id, results, task_output_dir)

    def _write_metrics_summary(self, task_id: str, results: list, task_output_dir: Path):
        per_segment = []
        tracking_fields = [
            "maje", "root_height_error", "root_pos_error", "root_rot_error",
            "velocity_error", "accel_error", "success_margin",
        ]
        tracking_vals: dict = {k: [] for k in tracking_fields}
        phase_lags = []
        trans_fields = ["seam_vel_delta", "seam_accel_delta", "peak_jerk", "mean_jerk", "auj"]
        trans_vals: dict = {k: [] for k in trans_fields}
        hermite_count = 0
        linear_count = 0

        for r in results:
            m = dataclasses.asdict(r.metrics) if r.metrics is not None else None
            seg_row: dict = {
                "segment_id": r.segment_id,
                "success": r.success,
            }
            if m:
                for k in tracking_fields:
                    v = m.get(k)
                    if v is not None:
                        tracking_vals[k].append(v)
                    seg_row[k] = v
                phase_lags.append(m.get("phase_lag_frame", 0))
                seg_row["phase_lag_frame"] = m.get("phase_lag_frame")
            else:
                for k in tracking_fields:
                    seg_row[k] = None
                seg_row["phase_lag_frame"] = None

            result_json_path = Path(r.log_path) if r.log_path else None
            if result_json_path and result_json_path.exists():
                try:
                    raw = json.loads(result_json_path.read_text(encoding="utf-8"))
                    tm = raw.get("transition_metrics")
                except Exception:
                    tm = None
            else:
                tm = None

            if tm:
                for k in trans_fields:
                    v = tm.get(k)
                    if v is not None:
                        trans_vals[k].append(v)
                    seg_row[k] = v
                if tm.get("interpolation_mode") == "hermite":
                    hermite_count += 1
                elif tm.get("interpolation_mode") == "linear":
                    linear_count += 1
            else:
                for k in trans_fields:
                    seg_row[k] = None

            per_segment.append(seg_row)

        def _safe_stat(vals, fn):
            return float(fn(vals)) if vals else None

        aggregate_tracking = {
            **{f"mean_{k}": _safe_stat(tracking_vals[k], np.mean) for k in tracking_fields},
            **{f"max_{k}": _safe_stat(tracking_vals[k], np.max)
               for k in ["maje", "root_height_error"]},
            "min_success_margin": _safe_stat(tracking_vals["success_margin"], np.min),
            "mean_phase_lag_frame": _safe_stat(phase_lags, np.mean),
            "max_phase_lag_frame": _safe_stat(phase_lags, np.max),
        }
        aggregate_transitions = {
            **{f"mean_{k}": _safe_stat(trans_vals[k], np.mean) for k in trans_fields},
            "max_seam_vel_delta": _safe_stat(trans_vals["seam_vel_delta"], np.max),
            "max_auj": _safe_stat(trans_vals["auj"], np.max),
            "mean_peak_jerk": _safe_stat(trans_vals["peak_jerk"], np.mean),
            "hermite_count": hermite_count,
            "linear_count": linear_count,
        }
        doc = {
            "task_id": task_id,
            "total_segments": len(results),
            "aggregate_tracking": aggregate_tracking,
            "aggregate_transitions": aggregate_transitions,
            "per_segment": per_segment,
        }
        (task_output_dir / "summary_metrics.json").write_text(
            json.dumps(doc, indent=2), encoding="utf-8"
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
