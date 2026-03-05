"""
BER (Building Energy Rating) utilities.

Parse, validate, and score BER ratings for Irish properties.
"""

from __future__ import annotations

from packages.shared.utils import BER_RATINGS_ORDERED

# BER rating to numeric score (lower = better energy efficiency)
BER_SCORES: dict[str, int] = {
    rating: idx for idx, rating in enumerate(BER_RATINGS_ORDERED)
}

# BER category groupings for analytics
BER_CATEGORIES = {
    "excellent": ["A1", "A2", "A3"],
    "good": ["B1", "B2", "B3"],
    "average": ["C1", "C2", "C3"],
    "below_average": ["D1", "D2"],
    "poor": ["E1", "E2", "F", "G"],
}


def ber_to_score(rating: str | None) -> int | None:
    """
    Convert a BER rating to a numeric score.

    Lower is better (A1=0, G=14).
    Returns None for unknown ratings.
    """
    if not rating:
        return None
    normalized = rating.strip().upper()
    return BER_SCORES.get(normalized)


def ber_category(rating: str | None) -> str | None:
    """Categorize BER rating into broad groups."""
    if not rating:
        return None
    normalized = rating.strip().upper()
    for cat, ratings in BER_CATEGORIES.items():
        if normalized in ratings:
            return cat
    return None


def ber_is_better_than(rating_a: str | None, rating_b: str | None) -> bool | None:
    """Check if rating_a is better (more efficient) than rating_b."""
    score_a = ber_to_score(rating_a)
    score_b = ber_to_score(rating_b)
    if score_a is None or score_b is None:
        return None
    return score_a < score_b


def ber_color_hex(rating: str | None) -> str:
    """Return a hex color for BER rating visualization."""
    score = ber_to_score(rating)
    if score is None:
        return "#999999"

    # Green (A) → Red (G) gradient
    colors = [
        "#00A651", "#00A651", "#00A651",  # A1-A3
        "#8CC63F", "#8CC63F", "#8CC63F",  # B1-B3
        "#FFF200", "#FFF200", "#FFF200",  # C1-C3
        "#F7941D", "#F7941D",             # D1-D2
        "#ED1C24", "#ED1C24",             # E1-E2
        "#BE1E2D",                        # F
        "#7F1416",                        # G
    ]
    if score < len(colors):
        return colors[score]
    return "#999999"
