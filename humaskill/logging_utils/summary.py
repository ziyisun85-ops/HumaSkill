"""Summary statistics generation and printing for HumaSkill.

Computes aggregate statistics from execution logs and prints them
in a human-readable format.
"""

from humaskill.utils.printing import print_section, print_info


def generate_summary(logs: list[dict]) -> dict:
    """Compute aggregate statistics from a list of execution log entries.

    Args:
        logs: List of execution log entry dicts.  Each entry must contain
            at least ``status``, ``skill``, ``source``, and ``duration``.

    Returns:
        A dict with keys:
        - ``total_duration`` (float): Sum of all item durations.
        - ``total_items`` (int): Number of log entries.
        - ``success_count`` (int): Entries with ``status == "success"``.
        - ``failed_count`` (int): Entries with ``status == "failed"``.
        - ``recover_count`` (int): Entries with ``source == "recovery_inserted"``.
        - ``skill_breakdown`` (dict[str, int]): Per-skill occurrence count.
        - ``recovery_triggered`` (bool): ``True`` if any recovery occurred.
        - ``pipeline_time`` (float): Same as ``total_duration``.
    """
    total_duration = sum(entry.get("duration", 0.0) for entry in logs)
    total_items = len(logs)
    success_count = sum(1 for e in logs if e.get("status") == "success")
    failed_count = sum(1 for e in logs if e.get("status") == "failed")
    recover_count = sum(
        1 for e in logs if e.get("source") == "recovery_inserted"
    )

    # Per-skill breakdown
    skill_breakdown: dict[str, int] = {}
    for entry in logs:
        skill_name = entry.get("skill", "unknown")
        skill_breakdown[skill_name] = skill_breakdown.get(skill_name, 0) + 1

    return {
        "total_duration": total_duration,
        "total_items": total_items,
        "success_count": success_count,
        "failed_count": failed_count,
        "recover_count": recover_count,
        "skill_breakdown": skill_breakdown,
        "recovery_triggered": recover_count > 0,
        "pipeline_time": total_duration,
    }


def print_summary(summary: dict, text: str = "", duration: float = 0.0) -> None:
    """Print a human-readable execution summary to stdout.

    Args:
        summary: Summary dict from ``generate_summary()``.
        text: The original request text (for display).
        duration: The requested target duration (for display).
    """
    print_section("HumaSkill — Execution Summary")

    # Request info
    if text:
        print_info(f"Request:       {text}")
    if duration > 0:
        print_info(f"Target:        {duration:.1f} s")

    # Counts
    print_info(f"Total items:   {summary['total_items']}")
    print_info(f"Success:       {summary['success_count']}")
    if summary["failed_count"] > 0:
        print_info(f"Failed:        {summary['failed_count']}")
    else:
        print_info("Failed:        0")
    if summary["recover_count"] > 0:
        print_info(f"Recoveries:    {summary['recover_count']}")
    else:
        print_info("Recoveries:    0")

    # Skill breakdown
    print_info("Skill breakdown:")
    for skill_name, count in sorted(summary["skill_breakdown"].items()):
        print(f"    {skill_name:<20s} {count}")

    # Pipeline time
    print_info(f"Pipeline time: {summary['pipeline_time']:.2f} s")

    # Recovery warning
    if summary["recovery_triggered"]:
        print_info(
            "WARNING: One or more recovery operations were triggered "
            "during execution."
        )
