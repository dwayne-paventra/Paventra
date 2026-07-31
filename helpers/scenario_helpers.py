"""
Scenario planning helper functions for Paventra.
"""

from __future__ import annotations

import pandas as pd

from helpers.cost_helpers import calculate_project_cost

def calculate_high_risk_program(
    roads: pd.DataFrame,
) -> dict:
    """
    Calculate the cost and impact of repairing
    every High Risk road.
    """

    high_risk = roads[
        roads["Risk Level"] == "High"
    ]

    road_count = len(high_risk)

    total_cost = 0.0
    total_lane_miles = 0.0

    for _, road in high_risk.iterrows():

        lane_miles, cost = calculate_project_cost(
            road
        )

        total_lane_miles += lane_miles
        total_cost += cost

    average_risk_before = (
        high_risk["Risk Score"].mean()
        if road_count > 0
        else 0
    )

    return {
        "road_count": road_count,
        "lane_miles": total_lane_miles,
        "total_cost": total_cost,
        "average_risk_before": average_risk_before,
    }