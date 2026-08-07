"""
Executive dashboard metrics.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd


def render_dashboard_metrics(
    roads: pd.DataFrame,
    optimizer_results: dict,
) -> None:

    st.subheader("📊 Network Overview")

    total_roads = len(roads)

    high_risk = len(
        roads[
            roads["Risk Score"] >= 80
        ]
    )

    total_cost = roads[
        "Estimated Cost"
    ].sum()

    ai_selected = len(
        optimizer_results["roads"]
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "🛣 Total Roads",
            total_roads,
        )

    with col2:
        st.metric(
            "🚨 High Risk Roads",
            high_risk,
        )

    with col3:
        st.metric(
            "💰 Estimated Repair Cost",
            f"${total_cost:,.0f}",
        )

    with col4:
        st.metric(
            "⭐ AI Selected",
            ai_selected,
        )

    st.divider()