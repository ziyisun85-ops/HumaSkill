"""Formatted printing helpers for HumaSkill."""


def print_section(title: str) -> None:
    """Print a formatted section header with separator lines.

    Args:
        title: The section title text.
    """
    line = "=" * 60
    print(f"\n{line}")
    print(f"  {title}")
    print(f"{line}\n")


def print_info(msg: str) -> None:
    """Print an informational message prefixed with [INFO].

    Args:
        msg: The informational message.
    """
    print(f"[INFO] {msg}")


def print_error(msg: str) -> None:
    """Print an error message prefixed with [ERROR].

    Args:
        msg: The error message.
    """
    print(f"[ERROR] {msg}")
