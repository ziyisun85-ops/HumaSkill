"""Execution log saving for HumaSkill.

Provides ``save_execution_log()`` for persisting structured JSON logs
and ``build_log_item()`` for constructing individual log entries that
match INTERFACES.md §5 exactly.
"""

from humaskill.backends.base_backend import ExecutionResult
from humaskill.utils.io import save_json


def build_log_item(
    index: int,
    item: dict,
    result: ExecutionResult,
    start_time: float,
    end_time: float,
) -> dict:
    """Build a single execution log entry from a sequence item and its result.

    The returned dict matches INTERFACES.md §5 exactly — every field
    is present, using ``None`` for fields that are not available.

    Args:
        index: Zero-based position in the execution sequence.
        item: Repaired sequence item dict with ``skill``, ``duration``, ``source``.
        result: ``ExecutionResult`` from the backend.
        start_time: Cumulative start time for this item.
        end_time: Cumulative end time (start_time + duration).

    Returns:
        A dict with all 11 required log fields.
    """
    return {
        "index": index,
        "skill": result.skill,
        "duration": result.duration,
        "source": item.get("source", "agent"),
        "status": result.status,
        "start_time": start_time,
        "end_time": end_time,
        "backend_steps": result.steps,
        "backend_reward": result.reward,
        "failure_reason": result.failure_reason,
        "backend_info": result.info,
    }


def save_execution_log(
    logs: list[dict],
    sequence: list[dict],
    summary: dict,
    request: dict,
    output_path: str,
) -> None:
    """Save execution logs as a structured JSON file.

    The output file contains four top-level sections: ``request``
    (CLI parameters), ``sequence`` (the repaired skill sequence),
    ``logs`` (per-item execution entries), and ``summary`` (aggregate
    statistics).

    Args:
        logs: List of execution log entry dicts from the executor.
        sequence: The repaired skill sequence that was executed.
        summary: Summary statistics dict from ``generate_summary()``.
        request: Dict with CLI request metadata (text, duration, seed,
            fail_prob, backend).
        output_path: Path where the JSON file will be written.
    """
    data = {
        "request": request,
        "sequence": sequence,
        "logs": logs,
        "summary": summary,
    }
    save_json(output_path, data)
