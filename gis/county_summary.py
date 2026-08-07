"""
County summary utilities for Paventra.
"""

from __future__ import annotations

import pandas as pd


def build_county_summary(
    roads: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build county-level statistics from the road inventory.
    """

    summary = (
        roads
        .groupby("County")
        .agg(
            Roads=("Road ID", "count"),
            Average_Risk=("Risk Score", "mean"),
            Average_Condition=("Condition", "mean"),
            Average_ADT=("ADT", "mean"),
        )
        .reset_index()
    )

    summary["Average_Risk"] = (
        summary["Average_Risk"]
        .round(1)
    )

    summary["Average_Condition"] = (
        summary["Average_Condition"]
        .round(1)
    )

    summary["Average_ADT"] = (
        summary["Average_ADT"]
        .round(0)
        .astype(int)
    )

    return summary
