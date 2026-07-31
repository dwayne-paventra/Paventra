"""
Road Asset Details / Inventory Panel
"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def render_inventory_panel(
    road: pd.Series,
) -> None:
    """
    Render selected road details.
    """

    st.subheader("🛣 Road Asset Details")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Length",
            f"{road['Road Length']} mi",
        )

        st.metric(
            "Lanes",
            int(road["Lanes"]),
        )

    with col2:
        st.metric(
            "Traffic",
            road["Traffic"],
        )

        st.metric(
            "Condition",
            road["Condition"],
        )

    with col3:
        st.metric(
            "Risk Level",
            road["Risk Level"],
        )

        st.metric(
            "Treatment",
            road["Treatment"],
        )

    st.divider()

    st.markdown("### Selected Road")

    st.dataframe(
        pd.DataFrame([road]),
        use_container_width=True,
        hide_index=True,
    )