"""
Budget Panel component.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from helpers.cost_helpers import calculate_project_cost
from helpers.cost_helpers import calculate_project_budget
from helpers.cost_helpers import create_budget_chart


def render_budget_panel(
    road: pd.Series,
) -> float:
    """
    Render budget estimator.

    Returns
    -------
    float
        Estimated project cost.
    """

    st.subheader("💰 Maintenance Cost Estimator")

    lane_miles, estimated_cost = calculate_project_cost(
        road
    )

    left, right = st.columns(2)

    with left:

        st.metric(
            "Estimated Project Cost",
            f"${estimated_cost:,.0f}",
        )

    with right:

        st.metric(
            "Lane Miles",
            f"{lane_miles:.1f}",
        )

    st.markdown(
        "### 📊 Executive Budget Breakdown"
    )

    budget_df, _ = calculate_project_budget(
        road["Risk Level"]
    )

    st.dataframe(
        budget_df.style.hide(axis="index").format(
            {
                "Cost ($)": "${:,.0f}"
            }
        ),
        use_container_width=True,
    )

    st.plotly_chart(
        create_budget_chart(budget_df),
        use_container_width=True,
    )

    st.divider()

    return estimated_cost