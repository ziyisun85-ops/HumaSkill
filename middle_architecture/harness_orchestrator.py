import dataclasses
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Optional

import numpy as np

from middle_architecture.evaluation import SegmentMetrics
from middle_architecture.execution_monitor import ExecutionMonitor
from middle_architecture.matcher import MotionMatcher
from middle_architecture.gmt_motion_adapter import get_kinematic_frame
from low_level_execution.tracker_adapter import GMTTrackerAdapter, load_tracker_spec
from middle_architecture.canonical import CanonicalReference
from middle_architecture.reference_ops import (
    concat_reference_frames,
    interpolate_reference_frames,
    compute_transition_metrics,
    reanchor_kinematic_frame,
    reanchor_reference_frames,
    slice_motion_to_reference_frames,
)
from middle_architecture.robot_state import MatchConfig, ReferenceFrames, ReferenceSegment, RobotState, TransitionMetrics
from middle_architecture.skill_motion import SkillMotionLibraryAdapter
from middle_architecture.recovery_manager import RecoveryManager
from middle_architecture.transition_builder import TransitionBuilder
from middle_architecture.transition_planner import TransitionPlan, TransitionPlanner


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
    diagnostics: Optional[dict] = None


class HarnessOrchestrator:
    def __init__(self, runner, skill_registry, transition_registry, motion_adapter, config):
        self.runner = runner
        self.skill_registry = skill_registry
        self.transition_registry = transition_registry
        self.motion_adapter = motion_adapter
        self.config = config or {}
        self.skillmotion_config = self.config.get("skillmotion", {}) or {}
        self.skillmotion_enabled = bool(self.skillmotion_config.get("enabled", False))
        self.runtime_motion_adapter = motion_adapter
        self.skillmotion_adapter = None
        self.tracker_adapter = None
        if self.skillmotion_enabled:
            self.skillmotion_adapter = SkillMotionLibraryAdapter(
                self.skillmotion_config.get("library_root", "skillmotion_library"),
                skill_registry,
            )
            self.runtime_motion_adapter = self.skillmotion_adapter
            self.tracker_adapter = GMTTrackerAdapter(
                runner,
                load_tracker_spec(
                    self.skillmotion_config.get("tracker_spec", "configs/trackers/gmt_g1.yaml")
                ),
            )
        m = self.config.get("matching", {})
        match_config = MatchConfig(
            mode=m.get("mode", "static"),
            search_window=int(m.get("search_window", 60)),
            score_weights=m.get("score_weights"),
        )
        self.matcher = MotionMatcher(match_config=match_config)
        self.transition_builder = TransitionBuilder(
            motion_source=skill_registry,
            motion_adapter=self.runtime_motion_adapter,
        )
        self.transition_planner = TransitionPlanner(
            skill_registry=skill_registry,
            motion_adapter=self.runtime_motion_adapter,
            config=self.config.get("transition_planner", {}),
        )
        runtime = self.config.get("runtime", {})
        self.output_root = Path(runtime.get("output_root", "outputs"))
        self.stop_on_failure = bool(runtime.get("stop_on_failure", True))
        self.reference_contract = self.config.get("reference_contract", {})
        monitor_config = self.config.get("execution_monitor", {}) or {}
        self.execution_monitor_enabled = bool(monitor_config.get("enabled", False))
        self.execution_monitor = (
            ExecutionMonitor(monitor_config) if self.execution_monitor_enabled else None
        )
        self.recovery_manager = (
            RecoveryManager(
                (monitor_config.get("recovery") or {}),
                skillmotion_adapter=self.skillmotion_adapter,
            )
            if self.execution_monitor_enabled
            else None
        )
        self.recovery_events = []

    def execute(self, skill_plan) -> list:
        self._initialize_tracker()
        task_output_dir = self.output_root / skill_plan.task_id
        task_output_dir.mkdir(parents=True, exist_ok=True)

        results = []
        state = self._get_robot_state()
        previous_skill = None
        transition_count = 0

        stabilization_segment = self._build_initial_stabilization_segment(state)
        if stabilization_segment is not None:
            if bool(self.config.get("initial_stabilization", {}).get("reset_to_stand_ready", False)):
                reset_fn = getattr(self.runner, "reset_to_reference_frame", None)
                if reset_fn is not None:
                    reset_fn(stabilization_segment.reference_frames)
                    state = self.runner.get_robot_state()
            stabilization_result = self._execute_segment(stabilization_segment, task_output_dir)
            results.append(stabilization_result)
            state = stabilization_result.final_state
            if not stabilization_result.success and self.stop_on_failure:
                self._write_summary(skill_plan.task_id, results, task_output_dir)
                return results

        for index, item in enumerate(skill_plan.sequence, start=1):
            skill_spec = self.skill_registry.get(item.skill)
            motion = self._load_motion_for_skill(item.skill, skill_spec)
            match = self.matcher.select(
                robot_state=state,
                skill_spec=skill_spec,
                motion=motion,
                duration=item.duration,
            )

            if previous_skill is not None:
                transition_count += 1
                fallback_spec = self.transition_registry.get(previous_skill, item.skill)
                transition_plan = self.transition_planner.plan(
                    fallback_spec=fallback_spec,
                    robot_state=state,
                    next_skill_spec=skill_spec,
                    next_motion=motion,
                    match=match,
                )
                transition_spec = transition_plan.spec
                tag = f"transition_{transition_count:03d}_{previous_skill}_to_{item.skill}"

                if transition_spec.mode == "bridge":
                    body_seg = self.transition_builder.build_bridge_body(
                        transition_spec, state
                    )
                    body_seg.segment_id = f"{tag}_body"
                    self._attach_transition_plan(body_seg, transition_plan)
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
                        self._attach_transition_plan(post_seg, transition_plan)
                        future_frames = self._prepare_skill_frames(
                            motion,
                            match,
                            self._reference_tail_state(post_seg.reference_frames),
                        )
                        self._attach_transition_metrics(
                            post_seg,
                            future_frames,
                            (post_seg.metadata or {}).get("post_interpolation_mode", "hermite"),
                        )
                        post_result = self._execute_segment(
                            post_seg,
                            task_output_dir,
                            future_reference_frames=future_frames,
                        )
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
                    self._attach_transition_plan(transition_segment, transition_plan)
                    future_frames = self._prepare_skill_frames(
                        motion,
                        match,
                        self._reference_tail_state(transition_segment.reference_frames),
                    )
                    self._attach_transition_metrics(
                        transition_segment,
                        future_frames,
                        transition_spec.interpolation_mode,
                    )
                    result = self._execute_segment(
                        transition_segment,
                        task_output_dir,
                        future_reference_frames=future_frames,
                    )
                    results.append(result)
                    state = result.final_state
                    if not result.success and self.stop_on_failure:
                        self._write_summary(skill_plan.task_id, results, task_output_dir)
                        return results

            skill_frames = self._prepare_skill_frames(motion, match, state)

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
                metadata={
                    "motion_source": self._motion_source_block(item.skill, skill_spec)
                },
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

    def _prepare_skill_frames(self, motion, match, anchor_state) -> ReferenceFrames:
        skill_frames = slice_motion_to_reference_frames(
            motion,
            match.start_frame,
            match.end_frame,
        )
        if self.reference_contract.get("reanchor_skill_clip") is True:
            skill_frames = reanchor_reference_frames(
                skill_frames,
                anchor_state,
                {
                    "root_reference_mode": self.reference_contract.get(
                        "root_reference_mode", "root_relative"
                    ),
                    "reanchor_yaw_only": self.reference_contract.get(
                        "reanchor_yaw_only", True
                    ),
                },
            )
        return skill_frames

    def _build_initial_stabilization_segment(self, state) -> Optional[ReferenceSegment]:
        config = self.config.get("initial_stabilization", {})
        if not bool(config.get("enabled", False)):
            return None

        stand_skill_name = config.get("stand_ready_skill", "stable_stand_bridge")
        blend_frames = int(config.get("blend_frames", 20))
        hold_frames = int(config.get("hold_frames", 40))
        if blend_frames <= 0 and hold_frames <= 0:
            return None

        stand_skill = self.skill_registry.get(stand_skill_name)
        stand_motion = self._load_motion_for_skill(stand_skill_name, stand_skill)
        stand_idx = int(stand_skill.default_start_frame)
        stand_frame = get_kinematic_frame(stand_motion, stand_idx)
        anchored_stand = reanchor_kinematic_frame(stand_frame, state)
        if bool(config.get("preserve_initial_root_height", True)):
            anchored_stand.root_pos = anchored_stand.root_pos.copy()
            anchored_stand.root_pos[2] = np.asarray(state.root_pos, dtype=np.float32)[2]
        reset_to_stand_ready = bool(config.get("reset_to_stand_ready", False))

        parts = []
        if reset_to_stand_ready:
            parts.append(
                interpolate_reference_frames(
                    anchored_stand,
                    anchored_stand,
                    num_frames=max(1, blend_frames + hold_frames),
                    fps=stand_motion.fps,
                )
            )
        elif blend_frames > 0:
            parts.append(
                interpolate_reference_frames(
                    state,
                    anchored_stand,
                    num_frames=blend_frames,
                    fps=stand_motion.fps,
                )
            )
        if not reset_to_stand_ready and hold_frames > 0:
            parts.append(
                interpolate_reference_frames(
                    anchored_stand,
                    anchored_stand,
                    num_frames=hold_frames,
                    fps=stand_motion.fps,
                )
            )

        return ReferenceSegment(
            segment_id="stabilization_000_stand_ready",
            segment_type="stabilization",
            skill_name=stand_skill_name,
            reference_frames=concat_reference_frames(parts),
            source_motion_path=stand_skill.motion_file,
            start_frame=stand_idx,
            end_frame=stand_idx,
            transition_type="initial_stabilization",
            reason="hold_stand_ready_before_first_skill",
            metadata={
                "blend_frames": blend_frames,
                "hold_frames": hold_frames,
                "stand_ready_skill": stand_skill_name,
                "control_mode": config.get("control_mode", "policy"),
                "action_ramp_steps": int(config.get("action_ramp_frames", 0)),
                "motion_source": self._motion_source_block(stand_skill_name, stand_skill),
            },
        )

    def _initialize_tracker(self) -> None:
        if self.tracker_adapter is not None:
            self.tracker_adapter.initialize()
        else:
            self.runner.initialize()

    def _get_robot_state(self) -> RobotState:
        if self.tracker_adapter is not None:
            return self.tracker_adapter.get_state().to_robot_state()
        return self.runner.get_robot_state()

    def _track_segment(
        self,
        reference_frames: ReferenceFrames,
        future_reference_frames: Optional[ReferenceFrames],
        kwargs: dict,
    ):
        if self.tracker_adapter is not None:
            return self.tracker_adapter.track(
                CanonicalReference.from_reference_frames(reference_frames),
                **kwargs,
            )
        return self.runner.track(
            reference_frames,
            **kwargs,
        )

    def _load_motion_for_skill(self, skill_name: str, skill_spec):
        if self.skillmotion_adapter is not None:
            return self.skillmotion_adapter.load_for_skill(skill_name)
        return self.motion_adapter.load(skill_spec.motion_file)

    def _motion_source_block(self, skill_name: Optional[str], skill_spec=None) -> dict:
        if skill_name is not None and self.skillmotion_adapter is not None:
            return self.skillmotion_adapter.motion_source_block(skill_name)
        if self.skillmotion_adapter is not None:
            return {
                "type": "skillmotion",
                "library_entry": None,
                "source_type": "generated_reference",
                "source_asset": None,
                "role": None,
            }
        return {
            "type": "registry",
            "library_entry": None,
            "source_type": "qpos_clip",
            "source_asset": getattr(skill_spec, "motion_file", None),
            "role": None,
        }

    def _attach_transition_plan(self, segment: ReferenceSegment, plan: TransitionPlan) -> None:
        metadata = dict(segment.metadata or {})
        metadata["transition_plan"] = {
            "decision": plan.decision,
            "reason": plan.reason,
            "diagnostics": plan.diagnostics,
        }
        segment.metadata = metadata

    def _attach_transition_metrics(
        self,
        segment: ReferenceSegment,
        next_skill_frames: ReferenceFrames,
        interpolation_mode: str,
    ) -> None:
        metadata = dict(segment.metadata or {})
        metadata["transition_metrics"] = compute_transition_metrics(
            segment.reference_frames,
            next_skill_frames,
            interpolation_mode,
        )
        segment.metadata = metadata

    def _reference_tail_state(self, reference_frames: ReferenceFrames) -> RobotState:
        root_rot = reference_frames.root_rot[-1]
        return RobotState(
            root_pos=reference_frames.root_pos[-1].copy(),
            root_quat=np.array([root_rot[3], root_rot[0], root_rot[1], root_rot[2]], dtype=np.float32),
            dof_pos=reference_frames.dof_pos[-1].copy(),
            root_lin_vel=np.zeros(3, dtype=np.float32),
            root_ang_vel=np.zeros(3, dtype=np.float32),
            dof_vel=np.zeros(reference_frames.dof_pos.shape[1], dtype=np.float32),
        )

    def _execute_segment(
        self,
        segment: ReferenceSegment,
        task_output_dir: Path,
        future_reference_frames: Optional[ReferenceFrames] = None,
    ) -> ExecutionResult:
        segment_dir = task_output_dir / segment.segment_id
        segment_dir.mkdir(parents=True, exist_ok=True)
        track_result = self._track_segment(
            segment.reference_frames,
            future_reference_frames,
            self._runner_track_kwargs(segment, future_reference_frames),
        )
        final_state = self._get_robot_state()
        self._write_robot_state(final_state, segment_dir / "robot_state_final.npz")

        result_json = segment_dir / "result.json"
        seg_metrics = track_result.metrics
        diagnostics = getattr(track_result, "diagnostics", None) or {}
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
            "diagnostics": diagnostics,
            "transition_metrics": dataclasses.asdict(trans_metrics_raw)
            if isinstance(trans_metrics_raw, TransitionMetrics)
            else trans_metrics_raw,
            "transition_plan": (segment.metadata or {}).get("transition_plan"),
            "motion_source": (segment.metadata or {}).get("motion_source")
            or self._motion_source_block(segment.skill_name),
        }
        recovery_block = self._monitor_segment(
            segment,
            track_result,
            final_state,
            trans_metrics_raw,
        )
        payload["recovery"] = recovery_block
        result_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._write_recovery_events(task_output_dir)

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
            diagnostics=diagnostics,
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
                    "diagnostics": result.diagnostics or {},
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
        self._write_recovery_events(task_output_dir)

    def _write_metrics_summary(self, task_id: str, results: list, task_output_dir: Path):
        per_segment = []
        tracking_fields = [
            "maje", "root_height_error", "root_pos_error", "root_rot_error",
            "velocity_error", "accel_error", "success_margin",
            "max_abs_roll", "max_abs_pitch", "mean_qvel_norm", "max_qvel_norm",
            "mean_root_velocity_norm", "max_root_velocity_norm",
            "foot_contact_switch_count", "foot_contact_consistency", "foot_sliding",
        ]
        tracking_vals: dict = {k: [] for k in tracking_fields}
        phase_lags = []
        trans_fields = [
            "seam_vel_delta", "seam_accel_delta", "peak_jerk", "mean_jerk", "auj",
            "root_position_jump", "root_yaw_jump_deg", "root_height_jump",
            "base_velocity_jump", "dof_position_jump_mean", "dof_position_jump_max",
            "phase_compatibility_score",
        ]
        trans_vals: dict = {k: [] for k in trans_fields}
        hermite_count = 0
        linear_count = 0

        for r in results:
            m = dataclasses.asdict(r.metrics) if r.metrics is not None else None
            seg_row: dict = {
                "segment_id": r.segment_id,
                "success": r.success,
            }
            if r.diagnostics:
                seg_row["first_second_stability"] = r.diagnostics.get("first_second_stability")
            else:
                seg_row["first_second_stability"] = None
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
               for k in [
                   "maje", "root_height_error", "max_abs_roll", "max_abs_pitch",
                   "max_qvel_norm", "max_root_velocity_norm", "foot_sliding",
               ]},
            "min_success_margin": _safe_stat(tracking_vals["success_margin"], np.min),
            "min_foot_contact_consistency": _safe_stat(
                tracking_vals["foot_contact_consistency"], np.min
            ),
            "mean_phase_lag_frame": _safe_stat(phase_lags, np.mean),
            "max_phase_lag_frame": _safe_stat(phase_lags, np.max),
        }
        aggregate_transitions = {
            **{f"mean_{k}": _safe_stat(trans_vals[k], np.mean) for k in trans_fields},
            "max_seam_vel_delta": _safe_stat(trans_vals["seam_vel_delta"], np.max),
            "max_auj": _safe_stat(trans_vals["auj"], np.max),
            "mean_peak_jerk": _safe_stat(trans_vals["peak_jerk"], np.mean),
            "max_root_position_jump": _safe_stat(trans_vals["root_position_jump"], np.max),
            "max_root_yaw_jump_deg": _safe_stat(trans_vals["root_yaw_jump_deg"], np.max),
            "max_base_velocity_jump": _safe_stat(trans_vals["base_velocity_jump"], np.max),
            "min_phase_compatibility_score": _safe_stat(
                trans_vals["phase_compatibility_score"], np.min
            ),
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

    def _runner_track_kwargs(
        self,
        segment: ReferenceSegment,
        future_reference_frames: Optional[ReferenceFrames],
    ) -> dict:
        kwargs = {
            "future_reference_frames": future_reference_frames,
            "segment_label": segment.segment_id,
        }
        control_mode = (segment.metadata or {}).get("control_mode", "policy")
        if control_mode != "policy":
            kwargs["control_mode"] = control_mode
        action_ramp_steps = int((segment.metadata or {}).get("action_ramp_steps", 0))
        if action_ramp_steps > 0:
            kwargs["action_ramp_steps"] = action_ramp_steps
        return kwargs

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

    def _monitor_segment(self, segment, track_result, final_state, transition_metrics) -> dict:
        if self.execution_monitor is None or self.recovery_manager is None:
            return {"enabled": False, "events": [], "recommendations": []}

        events = self.execution_monitor.analyze(
            segment=segment,
            track_result=track_result,
            final_state=final_state,
            transition_metrics=transition_metrics,
        )
        recommendations = self.recovery_manager.recommend(events)
        event_dicts = [event.to_dict() for event in events]
        recovery_block = {
            "enabled": True,
            "events": event_dicts,
            "recommendations": recommendations,
        }
        if event_dicts or recommendations:
            self.recovery_events.append(
                {
                    "segment_id": segment.segment_id,
                    "events": event_dicts,
                    "recommendations": recommendations,
                }
            )
        return recovery_block

    def _write_recovery_events(self, task_output_dir: Path) -> None:
        if not self.execution_monitor_enabled:
            return
        (task_output_dir / "recovery_events.json").write_text(
            json.dumps(self.recovery_events, indent=2), encoding="utf-8"
        )
