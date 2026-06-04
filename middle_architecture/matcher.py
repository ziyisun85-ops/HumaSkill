from dataclasses import dataclass
from typing import Optional


@dataclass
class MatchResult:
    motion_path: str
    start_frame: int
    end_frame: Optional[int]
    score: float
    reason: str


class MotionMatcher:
    def select(self, robot_state, skill_spec, motion, duration=None) -> MatchResult:
        start_frame = int(skill_spec.default_start_frame)
        if duration is not None:
            num_frames = int(round(float(duration) * float(motion.fps)))
            end_frame = min(start_frame + num_frames, motion.num_frames)
        else:
            end_frame = skill_spec.default_end_frame

        if end_frame is None:
            end_frame = motion.num_frames

        return MatchResult(
            motion_path=skill_spec.motion_file,
            start_frame=start_frame,
            end_frame=int(end_frame),
            score=0.0,
            reason="static_skill_spec_match",
        )
