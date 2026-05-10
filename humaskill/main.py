"""HumaSkill — CLI entry point for the skill-level composition pipeline.

Full pipeline:
    User CLI args → Composer → SequenceValidator → TransitionManager
    → SkillExecutor → ExecutionLogger → Summary → Print to stdout

Usage:
    python -m humaskill.main --text "跳一段 12 秒的欢快机器人舞蹈" \
        --duration 12 --seed 42 --fail-prob 0.1 --backend dummy \
        --output logs/demo_log.json
"""

import argparse
import sys
from pathlib import Path

from humaskill.skills.skill_registry import SkillRegistry
from humaskill.composer.rule_based_composer import RuleBasedDanceComposer
from humaskill.harness.sequence_validator import SequenceValidator
from humaskill.harness.transition_manager import TransitionManager
from humaskill.harness.skill_executor import SkillExecutor
from humaskill.logging_utils.execution_logger import save_execution_log
from humaskill.logging_utils.summary import generate_summary, print_summary


# ---------------------------------------------------------------------------
# Project root resolution
# ---------------------------------------------------------------------------

def _project_root() -> Path:
    """Return the absolute path to the project root directory.

    Resolves relative to this source file so the CLI works regardless
    of the current working directory.
    """
    return Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Backend factory
# ---------------------------------------------------------------------------

def create_backend(name: str, fail_prob: float, seed: int):
    """Create a backend instance by name.

    Only ``"dummy"`` is implemented in MVP.  All other backend names
    raise ``ValueError`` with a clear message.

    Args:
        name: Backend name (``"dummy"`` in MVP).
        fail_prob: Probability of execution failure (0.0–1.0).
        seed: Random seed for reproducible failure patterns.

    Returns:
        A ``BaseBackend`` instance.

    Raises:
        ValueError: If *name* is not a supported backend.
    """
    if name == "dummy":
        from humaskill.backends.dummy_backend import DummyDanceBackend
        return DummyDanceBackend(fail_prob=fail_prob, seed=seed)

    raise ValueError(
        f"Unknown backend: {name!r}. Supported backends: 'dummy'"
    )


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        prog="python -m humaskill.main",
        description=(
            "HumaSkill — skill-level composition and execution harness "
            "for language-guided humanoid motion composition."
        ),
    )

    parser.add_argument(
        "--text",
        type=str,
        required=True,
        help="Natural language instruction (Chinese).",
    )
    parser.add_argument(
        "--duration",
        type=float,
        required=True,
        help="Target total duration in seconds.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42).",
    )
    parser.add_argument(
        "--fail-prob",
        type=float,
        default=0.1,
        help="Probability of execution failure 0.0–1.0 (default: 0.1).",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="dummy",
        help="Execution backend name (default: 'dummy').",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to save execution logs as JSON (optional).",
    )

    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Run the full HumaSkill pipeline.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    args = parse_args(argv)

    project_root = _project_root()
    skills_yaml_path = project_root / "configs" / "skills.yaml"

    # 1. Load skill registry
    try:
        registry = SkillRegistry(str(skills_yaml_path))
    except Exception as exc:
        print(f"[ERROR] Failed to load skill registry: {exc}", file=sys.stderr)
        return 1

    # 2. Compose raw skill sequence
    try:
        composer = RuleBasedDanceComposer(registry)
        raw_sequence = composer.compose(args.text, args.duration, args.seed)
    except Exception as exc:
        print(f"[ERROR] Composition failed: {exc}", file=sys.stderr)
        return 1

    # 3. Validate raw sequence
    try:
        validator = SequenceValidator(registry)
        validator.validate(raw_sequence)
    except Exception as exc:
        print(f"[ERROR] Sequence validation failed: {exc}", file=sys.stderr)
        return 1

    # 4. Repair transitions
    try:
        transition_mgr = TransitionManager(registry)
        repaired_sequence = transition_mgr.repair(raw_sequence)
    except Exception as exc:
        print(f"[ERROR] Transition repair failed: {exc}", file=sys.stderr)
        return 1

    # 5. Execute
    try:
        backend = create_backend(args.backend, args.fail_prob, args.seed)
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    try:
        executor = SkillExecutor(backend, registry)
        logs, _executor_summary = executor.execute_sequence(repaired_sequence)
    except Exception as exc:
        print(f"[ERROR] Execution failed: {exc}", file=sys.stderr)
        return 1

    # 6. Generate summary
    summary = generate_summary(logs)

    # 7. Save execution logs if --output was provided
    if args.output:
        output_path = Path(args.output)
        # Resolve relative paths against cwd to match user expectation.
        if not output_path.is_absolute():
            output_path = Path.cwd() / output_path
        save_execution_log(
            logs=logs,
            sequence=repaired_sequence,
            summary=summary,
            request={
                "text": args.text,
                "duration": args.duration,
                "seed": args.seed,
                "fail_prob": args.fail_prob,
                "backend": args.backend,
            },
            output_path=str(output_path),
        )
        print(f"[INFO] Execution log saved to: {output_path}")

    # 8. Print summary to stdout
    print_summary(summary, text=args.text, duration=args.duration)

    return 0


# ---------------------------------------------------------------------------
# __main__ guard
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())
