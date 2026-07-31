"""
Cost helper functions for Paventra.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px


_COST_PER_LANE_MILE = {
    "Crack Seal": 18_000,
    "Overlay": 180_000,
    "Reconstruction": 950_000,
    "Not Assigned": 0,
    "None": 0,
}


def calculate_lane_miles(road: pd.Series) -> float:
    """Calculate lane miles."""

    return float(road["Road Length"]) * float(road["Lanes"])


def calculate_project_cost(
    road: pd.Series,
) -> tuple[float, float]:
    """
    Calculate estimated project cost.

    Returns
    -------
    tuple
        (lane_miles, estimated_cost)
    """

    lane_miles = calculate_lane_miles(road)

    treatment = str(road["Treatment"])

    estimated_cost = (
        lane_miles
        * _COST_PER_LANE_MILE.get(treatment, 0)
    )

    return lane_miles, estimated_cost


def calculate_project_budget(
    risk_level: str,
) -> tuple[pd.DataFrame, float]:
    """
    Create a simple executive budget breakdown.
    """

    if risk_level == "High":
        values = [0.50, 0.30, 0.20]
    elif risk_level == "Medium":
        values = [0.35, 0.40, 0.25]
    else:
        values = [0.20, 0.30, 0.50]

    total = 1_000_000

    budget_df = pd.DataFrame(
        {
            "Category": [
                "Preventive",
                "Corrective",
                "Emergency",
            ],
            "Cost ($)": [
                total * values[0],
                total * values[1],
                total * values[2],
            ],
        }
    )

    return budget_df, total


def create_budget_chart(
    budget_df: pd.DataFrame,
):
    """
    Create executive budget chart.
    """

    fig = px.bar(
        budget_df,
        x="Category",
        y="Cost ($)",
        text="Cost ($)",
        title="Budget Allocation",
    )

    fig.update_traces(texttemplate="$%{y:,.0f}")

    return fig


def create_capital_chart(
    capital_df: pd.DataFrame,
):
    """
    Create capital improvement chart.
    """

    fig = px.bar(
        capital_df,
        x="Fiscal Year",
        y="Recommended Budget",
        text="Recommended Budget",
        title="Capital Improvement Plan",
    )

    fig.update_traces(texttemplate="$%{y:,.0f}")

    return fig