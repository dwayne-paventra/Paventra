"""
Dashboard metric calculations for Paventra.

This module is the single source of truth for all executive dashboard
statistics. UI components should consume the returned metrics dictionary
instead of performing their own calculations.
"""

from __future__ import annotations

import pandas as pd


def _safe_mean(series: pd.Series) -> float:
    """Return a rounded mean, or 0.0 if the series is empty."""
    if series.empty:
        return 0.0
    return round(float(series.mean()), 1)


def calculate_dashboard_metrics(roads: pd.DataFrame) -> dict:
    """
    Calculate all dashboard metrics from the road inventory.

    Parameters
    ----------
    roads : pandas.DataFrame
        Road inventory dataframe.

    Returns
    -------
    dict
        Dictionary containing all executive dashboard metrics.
    """

    if roads is None or roads.empty:
        return {
            "roads_total": 0,
            "avg_risk": 0.0,
            "high_risk": 0,
            "medium_risk": 0,
            "low_risk": 0,
            "average_pci": 0.0,
            "network_health": 0.0,
            "health_status": "No Data",
            "health_color": "#9E9E9E",
        }

    roads_total = len(roads)

    avg_risk = (
        _safe_mean(roads["Risk Score"])
        if "Risk Score" in roads.columns
        else 0.0
    )

    high_risk = (
        (roads["Risk Level"] == "High").sum()
        if "Risk Level" in roads.columns
        else 0
    )

    medium_risk = (
        (roads["Risk Level"] == "Medium").sum()
        if "Risk Level" in roads.columns
        else 0
    )

    low_risk = (
        (roads["Risk Level"] == "Low").sum()
        if "Risk Level" in roads.columns
        else 0
    )

    # Use PCI if available; otherwise estimate from Risk Score.
    if "PCI" in roads.columns:
        average_pci = _safe_mean(roads["PCI"])
    elif "Risk Score" in roads.columns:
        average_pci = round(
            float((100 - roads["Risk Score"]).clip(0, 100).mean()),
            1,
        )
    else:
        average_pci = 0.0

    # Executive Network Health Score
    network_health = round(
        (average_pci * 0.70)
        + ((1 - (high_risk / roads_total)) * 30),
        1,
    )

    network_health = max(0.0, min(100.0, network_health))

    if network_health >= 85:
        health_status = "Excellent"
        health_color = "#2E7D32"
    elif network_health >= 70:
        health_status = "Good"
        health_color = "#43A047"
    elif network_health >= 55:
        health_status = "Fair"
        health_color = "#F9A825"
    else:
        health_status = "Needs Attention"
        health_color = "#D32F2F"

    return {
        "roads_total": roads_total,
        "avg_risk": avg_risk,
        "high_risk": int(high_risk),
        "medium_risk": int(medium_risk),
        "low_risk": int(low_risk),
        "average_pci": average_pci,
        "network_health": network_health,
        "health_status": health_status,
        "health_color": health_color,
    }