"""
Charts and capital planning component.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from helpers.cost_helpers import create_capital_chart


def render_charts_panel(
    roads: pd.DataFrame,
    risk: str,
    estimated_cost: float,
) -> pd.DataFrame:
    """
    Render capital planning and executive charts.

    Returns
    -------
    pandas.DataFrame
        Capital improvement plan.
    """

    st.subheader("📅 Multi-Year Capital Improvement Plan")

    if risk == "High":
        allocations = (0.40, 0.35, 0.25)
    elif risk == "Medium":
        allocations = (0.30, 0.40, 0.30)
    else:
        allocations = (0.20, 0.30, 0.50)

    capital_df = pd.DataFrame(
        {
            "Fiscal Year": [
                "FY2026",
                "FY2027",
                "FY2028",
            ],
            "Recommended Budget": [
                estimated_cost * allocations[0],
                estimated_cost * allocations[1],
                estimated_cost * allocations[2],
            ],
        }
    )

    st.dataframe(
        capital_df.style.hide(axis="index").format(
            {"Recommended Budget": "${:,.0f}"}
        ),
        use_container_width=True,
    )

    st.plotly_chart(
        create_capital_chart(capital_df),
        use_container_width=True,
    )

    st.divider()

    left, right = st.columns(2)

    with left:
        risk_fig = px.pie(
            roads,
            names="Risk Level",
            title="Risk Distribution",
            color="Risk Level",
            color_discrete_map={
                "Low": "#2ECC71",
                "Medium": "#F39C12",
                "High": "#E74C3C",
            },
        )

        st.plotly_chart(
            risk_fig,
            use_container_width=True,
        )

    with right:
        condition_fig = px.bar(
            roads,
            x="Condition",
            title="Road Condition Breakdown",
            color="Condition",
        )

        st.plotly_chart(
            condition_fig,
            use_container_width=True,
        )

    st.divider()

    return capital_df