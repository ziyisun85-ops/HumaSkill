"""SkillExecutor for executing repaired sequences with recovery on failure.

Follows INTERFACES.md §5 and §13 strictly — logs use ExecutionResult.status,
never raw strings.
"""

from humaskill.backends.base_backend import BaseBackend, ExecutionResult
from humaskill.skills.skill_registry import SkillRegistry
from humaskill.utils.errors import UnknownSkillError


class SkillExecutor:
    """Executes a repaired skill sequence through a backend with recovery on failure.

    When a backend returns ExecutionResult with status "failed", the executor
    inserts a "recover" skill before the failed skill and retries the failed skill
    exactly once. The recover skill has source="recovery_inserted".
    Logs use structured ExecutionResult fields — never raw strings.
    """

    def __init__(self, backend: BaseBackend, registry: SkillRegistry):
        """Initialize the executor.

        Args:
            backend: Backend instance that executes individual skills.
            registry: SkillRegistry for looking up skill metadata (e.g., durations).
        """
        self._backend = backend
        self._registry = registry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute_sequence(
        self, sequence: list[dict]
    ) -> tuple[list[dict], dict]:
        """Execute a repaired skill sequence through the backend.

        Args:
            sequence: List of repaired sequence items. Each item is a dict
                      with keys: skill, duration, source.

        Returns:
            Tuple of (execution_logs, summary).
            execution_logs: list of log entry dicts.
            summary: dict with total_items, total_duration, planned_duration,
                     success_count, failed_count, recover_count, backend_name.
        """
        if not sequence:
            return [], self._empty_summary()

        logs: list[dict] = []
        current_time: float = 0.0
        recover_count: int = 0
        planned_duration: float = sum(item["duration"] for item in sequence)

        # We iterate manually (not with enumerate on sequence) because
        # recovery inserts may expand the logical iteration.
        i = 0
        while i < len(sequence):
            item = sequence[i]
            skill_name: str = item["skill"]
            duration: float = item["duration"]
            source: str = item.get("source", "agent")

            # Execute the skill.
            result = self._backend.execute(skill_name, duration)
            log_entry = self._build_log_entry(
                index=len(logs),
                skill=skill_name,
                duration=duration,
                source=source,
                result=result,
                start_time=current_time,
                end_time=current_time + duration,
            )
            logs.append(log_entry)
            current_time += duration

            # --- Recovery on failure ---
            if result.status == "failed":
                # Attempt recovery.
                recover_duration = self._recover_duration()
                recover_result = self._backend.execute("recover", recover_duration)

                recover_log = self._build_log_entry(
                    index=len(logs),
                    skill="recover",
                    duration=recover_duration,
                    source="recovery_inserted",
                    result=recover_result,
                    start_time=current_time,
                    end_time=current_time + recover_duration,
                )
                logs.append(recover_log)
                current_time += recover_duration
                recover_count += 1

                # Retry the failed skill exactly once.
                retry_result = self._backend.execute(skill_name, duration)
                retry_log = self._build_log_entry(
                    index=len(logs),
                    skill=skill_name,
                    duration=duration,
                    source=source,
                    result=retry_result,
                    start_time=current_time,
                    end_time=current_time + duration,
                )
                logs.append(retry_log)
                current_time += duration

            i += 1

        summary = self._build_summary(logs, planned_duration, recover_count)
        return logs, summary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_log_entry(
        self,
        index: int,
        skill: str,
        duration: float,
        source: str,
        result: ExecutionResult,
        start_time: float,
        end_time: float,
    ) -> dict:
        """Build a structured log entry from an ExecutionResult.

        Follows INTERFACES.md §5 exactly — all 11 required fields.
        status comes from ExecutionResult.status, never from raw strings.
        """
        return {
            "index": index,
            "skill": skill,
            "duration": duration,
            "source": source,
            "status": result.status,
            "start_time": start_time,
            "end_time": end_time,
            "backend_steps": result.steps,
            "backend_reward": result.reward,
            "failure_reason": result.failure_reason,
            "backend_info": result.info,
        }

    def _recover_duration(self) -> float:
        """Return the default duration for the recover skill.

        Uses the midpoint of the recover skill's duration_range from the registry.
        Raises UnknownSkillError if 'recover' is not registered.
        """
        if not self._registry.has("recover"):
            raise UnknownSkillError(
                "The 'recover' skill is not registered. "
                "It is required for execution recovery but was not found in the skill registry."
            )
        skill_info = self._registry.get("recover")
        lo, hi = skill_info.duration_range
        return (lo + hi) / 2.0

    def _build_summary(
        self,
        logs: list[dict],
        planned_duration: float,
        recover_count: int,
    ) -> dict:
        """Build the summary dict from completed execution logs.

        total_duration: sum of durations of non-recovery items only.
        """
        success_count = sum(1 for e in logs if e["status"] == "success")
        failed_count = sum(1 for e in logs if e["status"] == "failed")

        # total_duration excludes recovery-inserted items.
        total_duration = sum(
            e["duration"] for e in logs if e["source"] != "recovery_inserted"
        )

        return {
            "total_items": len(logs),
            "total_duration": total_duration,
            "planned_duration": planned_duration,
            "success_count": success_count,
            "failed_count": failed_count,
            "recover_count": recover_count,
            "backend_name": type(self._backend).__name__,
        }

    def _empty_summary(self) -> dict:
        """Return a zero-value summary for empty sequences."""
        return {
            "total_items": 0,
            "total_duration": 0.0,
            "planned_duration": 0.0,
            "success_count": 0,
            "failed_count": 0,
            "recover_count": 0,
            "backend_name": type(self._backend).__name__,
        }
