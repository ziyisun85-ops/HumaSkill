from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class ExecutionEvent:
    event_type: str
    severity: str
    segment_id: str
    message: str
    metric: Optional[str] = None
    value: Optional[float] = None
    threshold: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ExecutionMonitor:
    def __init__(self, config: Dict[str, Any] = None) -> None:
        self.config = config or {}
        self.low_success_margin = float(self.config.get("low_success_margin", 0.30))
        self.max_seam_velocity = float(self.config.get("max_seam_velocity", 0.10))
        self.max_abs_tilt = float(self.config.get("max_abs_tilt", 1.0))
        self.max_tracking_maje = float(self.config.get("max_tracking_maje", 0.20))

    def analyze(
        self,
        segment,
        track_result,
        final_state,
        transition_metrics=None,
    ) -> List[ExecutionEvent]:
        events: List[ExecutionEvent] = []
        segment_id = segment.segment_id

        if not bool(track_result.success) and track_result.failed_reason == "fell":
            events.append(
                ExecutionEvent(
                    event_type="fall_detected",
                    severity="error",
                    segment_id=segment_id,
                    metric="failed_reason",
                    message="runner reported a fall",
                )
            )

        metrics = getattr(track_result, "metrics", None)
        if metrics is not None:
            if float(metrics.success_margin) < self.low_success_margin:
                events.append(
                    ExecutionEvent(
                        event_type="low_success_margin",
                        severity="warning",
                        segment_id=segment_id,
                        metric="success_margin",
                        value=float(metrics.success_margin),
                        threshold=self.low_success_margin,
                        message="segment success margin is below warning threshold",
                    )
                )
            if max(abs(float(metrics.max_abs_roll)), abs(float(metrics.max_abs_pitch))) > self.max_abs_tilt:
                events.append(
                    ExecutionEvent(
                        event_type="tilt_exceeded",
                        severity="warning",
                        segment_id=segment_id,
                        metric="max_abs_roll_pitch",
                        value=max(abs(float(metrics.max_abs_roll)), abs(float(metrics.max_abs_pitch))),
                        threshold=self.max_abs_tilt,
                        message="segment tilt exceeded monitor threshold",
                    )
                )
            if float(metrics.maje) > self.max_tracking_maje:
                events.append(
                    ExecutionEvent(
                        event_type="tracking_error_high",
                        severity="warning",
                        segment_id=segment_id,
                        metric="maje",
                        value=float(metrics.maje),
                        threshold=self.max_tracking_maje,
                        message="mean absolute joint error exceeded monitor threshold",
                    )
                )

        if transition_metrics is not None:
            seam = getattr(transition_metrics, "seam_vel_delta", None)
            if seam is not None and float(seam) > self.max_seam_velocity:
                events.append(
                    ExecutionEvent(
                        event_type="seam_velocity_exceeded",
                        severity="warning",
                        segment_id=segment_id,
                        metric="seam_vel_delta",
                        value=float(seam),
                        threshold=self.max_seam_velocity,
                        message="transition seam velocity exceeded monitor threshold",
                    )
                )

        if final_state is not None and np.any(~np.isfinite(np.asarray(final_state.root_pos))):
            events.append(
                ExecutionEvent(
                    event_type="tracking_error_high",
                    severity="error",
                    segment_id=segment_id,
                    metric="final_root_pos",
                    message="final root position contains non-finite values",
                )
            )

        return events
