from typing import Any, Dict, Iterable, List, Optional


class RecoveryManager:
    def __init__(self, config: Dict[str, Any] = None, skillmotion_adapter=None) -> None:
        self.config = config or {}
        self.skillmotion_adapter = skillmotion_adapter
        self.default_reentry_skill = str(
            self.config.get("default_reentry_skill", "stable_stand_bridge")
        )

    def recommend(self, events: Iterable) -> List[Dict[str, Any]]:
        recommendations = []
        for event in events:
            event_type = getattr(event, "event_type", "")
            if event_type == "fall_detected":
                reentry_skill = self._safe_reentry_skill()
                recommendations.append(
                    {
                        "event_type": event_type,
                        "action": "recommend_reentry",
                        "execute": False,
                        "skill": reentry_skill,
                        "reason": "fall detected; log-only recovery manager recommends safe re-entry",
                    }
                )
            elif event_type in {
                "low_success_margin",
                "seam_velocity_exceeded",
                "tilt_exceeded",
                "tracking_error_high",
            }:
                recommendations.append(
                    {
                        "event_type": event_type,
                        "action": "monitor_only",
                        "execute": False,
                        "skill": None,
                        "reason": "warning event logged; no recovery action executed in phase 1",
                    }
                )
        return recommendations

    def _safe_reentry_skill(self) -> str:
        if self.skillmotion_adapter is None:
            return self.default_reentry_skill
        try:
            for skill_name in sorted(self.skillmotion_adapter.skill_registry.skills.keys()):
                motion = self.skillmotion_adapter.load_skillmotion(skill_name)
                if motion.role.recovery_tag == "safe_reentry":
                    return skill_name
        except Exception:
            return self.default_reentry_skill
        return self.default_reentry_skill
