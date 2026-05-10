"""Math utility functions for HumaSkill."""


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value to the inclusive range [min_val, max_val].

    Args:
        value: The value to clamp.
        min_val: The minimum allowed value.
        max_val: The maximum allowed value.

    Returns:
        The clamped value.

    Raises:
        ValueError: If min_val > max_val.
    """
    if min_val > max_val:
        raise ValueError(f"min_val ({min_val}) must not be greater than max_val ({max_val})")
    return max(min_val, min(value, max_val))
