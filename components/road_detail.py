"""
Road Detail component for Paventra.

This component is responsible for:
- Selecting a road
- Displaying the core road metrics
- Returning the selected road record

No AI, budgeting, or reporting logic belongs here.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def render_road_detail(roads: pd.DataFrame) -> pd.Series:
    """
    Render the Road Intelligence panel.

    Parameters
    ----------
    roads : pandas.DataFrame
        Complete road inventory.

    Returns
    -------
    pandas.Series
        Selected road record.
    """

    st.subheader("🛣 Road Intelligence")

    selected_road = st.selectbox(
        "Select a Road",
        roads["Road Name"],
    )

    road = roads.loc[
        roads["Road Name"] == selected_road
    ].iloc[0]

    left, right = st.columns(2)

    with left:
        st.metric("Risk Score", road["Risk Score"])
        st.metric("Risk Level", road["Risk Level"])
        st.metric("Condition", road["Condition"])

    with right:
        st.metric("Traffic", road["Traffic"])
        st.metric("Age", road["Age"])

        treatment = road["Treatment"]

        if (
            pd.isna(treatment)
            or str(treatment).lower() in ("none", "nan")
        ):
            treatment = "Not Assigned"

        st.metric("Treatment", treatment)

    st.markdown("---")

    return road