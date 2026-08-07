"""
GIS styling utilities.
"""

from __future__ import annotations

RISK_COLORS = {
    "high": "red",
    "medium": "orange",
    "moderate": "blue",
    "low": "green",
}

def risk_color(score: float) -> str:
    """Return marker color based on risk score."""

    if score >= 80:
        return RISK_COLORS["high"]

    if score >= 60:
        return RISK_COLORS["medium"]

    if score >= 40:
        return RISK_COLORS["moderate"]

    return RISK_COLORS["low"]