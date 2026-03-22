"""Utilities for safe money/financial value handling.

All monetary values should be treated as Decimal in the database and calculations.
This module provides safe conversion helpers between Decimal, float, and string representations.
"""

from decimal import Decimal, InvalidOperation
from typing import Any


class MoneyConversionError(ValueError):
    """Raised when money value cannot be safely converted."""

    pass


def to_decimal(value: Any, default: Decimal | None = None) -> Decimal | None:
    """Convert a value to Decimal safely.

    Args:
        value: Value to convert (Decimal, float, int, str, or None)
        default: Default value if conversion fails

    Returns:
        Decimal representation or default on failure
        
    Raises:
        MoneyConversionError: If value cannot be converted and no default provided
    """
    if value is None:
        return default

    if isinstance(value, Decimal):
        return value

    try:
        # Convert to string for Decimal to avoid float precision issues
        if isinstance(value, float):
            return Decimal(str(value))
        if isinstance(value, int):
            return Decimal(value)
        if isinstance(value, str):
            return Decimal(value)
        # Try string conversion for other types
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        if default is not None:
            return default
        raise MoneyConversionError(f"Cannot convert {type(value).__name__}({value!r}) to Decimal") from exc


def to_float(value: Any, default: float | None = None) -> float | None:
    """Convert a Decimal/numeric value to float safely.

    Use this only for JSON serialization and API responses, NOT for calculations.

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        Float representation or default on failure
    """
    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        if default is not None:
            return default
        raise MoneyConversionError(f"Cannot convert {type(value).__name__}({value!r}) to float") from exc


def safe_price_difference(current: Any, previous: Any, tolerance: Decimal | None = None) -> Decimal | None:
    """Calculate safe price difference between Decimal/numeric values.

    Args:
        current: Current price
        previous: Previous price
        tolerance: If provided, return None if abs(difference) <= tolerance

    Returns:
        The difference as Decimal, or None if below tolerance or either value is None
    """
    if current is None or previous is None:
        return None

    current_dec = to_decimal(current)
    previous_dec = to_decimal(previous)

    if current_dec is None or previous_dec is None:
        return None

    difference = current_dec - previous_dec

    if tolerance is not None and abs(difference) <= tolerance:
        return None

    return difference


def safe_price_pct_change(current: Any, previous: Any) -> float | None:
    """Calculate safe percentage change in price.

    Args:
        current: Current price
        previous: Previous price

    Returns:
        Percentage change as float, or None if either value is None or previous is zero
    """
    if current is None or previous is None:
        return None

    current_dec = to_decimal(current)
    previous_dec = to_decimal(previous)

    if current_dec is None or previous_dec is None or previous_dec == 0:
        return None

    change = (current_dec - previous_dec) / previous_dec * Decimal(100)
    return float(change)
