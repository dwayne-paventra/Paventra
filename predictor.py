"""Transparent, rules-based pavement risk scoring."""

from __future__ import annotations

import numbers


def _condition_contribution(condition, pci=None) -> tuple[int, str]:
    """Score condition, preferring an actual PCI value whenever supplied."""

    value = pci if pci is not None else condition
    if isinstance(value, numbers.Real) and not isinstance(value, bool):
        if value <= 40:
            return 40, f"PCI is {value:.0f}, indicating poor pavement condition"
        if value <= 55:
            return 30, f"PCI is {value:.0f}, indicating fair-to-poor pavement condition"
        if value <= 70:
            return 20, f"PCI is {value:.0f}, indicating fair pavement condition"
        return 0, f"PCI is {value:.0f}, indicating comparatively good pavement condition"

    label = str(value).strip().lower()
    if label == "poor":
        return 40, "condition is classified as Poor"
    if label == "fair":
        return 20, "condition is classified as Fair"
    return 0, "condition is classified as Good or is not elevated"


def calculate_risk_details(condition, traffic, age, freeze, pci=None, adt=None) -> dict:
    """Return a score, level, contributions, and a plain-language explanation.

    PCI and risk remain distinct. PCI describes pavement condition; risk combines
    condition with operational exposure factors. ``adt`` is accepted for future
    calibration but is intentionally not scored in this Phase 1 ruleset.
    """

    contributions = []
    condition_score, condition_reason = _condition_contribution(condition, pci)
    if condition_score:
        contributions.append((condition_score, condition_reason))

    traffic_score = {"high": 25, "medium": 10}.get(str(traffic).strip().lower(), 0)
    if traffic_score:
        contributions.append((traffic_score, f"traffic exposure is {str(traffic).title()}"))

    age_value = float(age)
    age_score = 20 if age_value >= 15 else 10 if age_value >= 10 else 0
    if age_score:
        contributions.append((age_score, f"asset age is {age_value:.0f} years"))

    freeze_score = {"high": 15, "medium": 8}.get(str(freeze).strip().lower(), 0)
    if freeze_score:
        contributions.append((freeze_score, f"freeze-thaw exposure is {str(freeze).title()}"))

    score = min(100, sum(points for points, _ in contributions))
    level = "High" if score >= 80 else "Medium" if score >= 60 else "Low"
    reason = "; ".join(reason for _, reason in contributions) or "no elevated risk factors were identified"
    return {"score": score, "level": level, "reason": reason, "contributions": contributions}


def calculate_risk(condition, traffic, age, freeze, pci=None):
    """Backward-compatible numeric score wrapper for legacy callers."""

    return calculate_risk_details(condition, traffic, age, freeze, pci=pci)["score"]

def risk_level(score):
    if score >= 70:
        return "High"
    elif score >= 40:
        return "Medium"
    else:
        return "Low"
