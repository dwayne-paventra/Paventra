"""
Data preparation helpers for Paventra.
"""

from __future__ import annotations

import pandas as pd


def create_risk_level(score: float) -> str:
    """
    Convert a numeric Risk Score into a Risk Level.
    """

    if score >= 80:
        return "High"

    if score >= 60:
        return "Medium"

    return "Low"


def prepare_road_data(roads: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare the road dataset for the application.

    This function standardizes data types and creates
    derived fields used throughout Paventra.
    """

    roads = roads.copy()

    # -----------------------------
    # Numeric columns
    # -----------------------------

    numeric_columns = [
        "Risk Score",
        "Latitude",
        "Longitude",
        "Road Length",
        "Lanes",
        "Speed Limit",
        "ADT",
    ]

    for column in numeric_columns:

        roads[column] = pd.to_numeric(
            roads[column],
            errors="coerce",
        )

    # -----------------------------
    # Derived columns
    # -----------------------------

    roads["Risk Level"] = roads["Risk Score"].apply(
        create_risk_level
    )

    roads["Lane Miles"] = (
        roads["Road Length"]
        * roads["Lanes"]
    )

    # -----------------------------
    # Fill missing values
    # -----------------------------

    roads = roads.fillna(
        {
            "Traffic": "Unknown",
            "Treatment": "Not Assigned",
            "Surface Type": "Unknown",
        }
    )

    return roads