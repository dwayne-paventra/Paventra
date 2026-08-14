"""City-facing recommendation table for the Jackson Pilot."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pilot.jackson_config import ACTIVE_MUNICIPALITY


def render_jackson_recommendations(results: dict) -> None:
    st.subheader("3. Recommended investments")
    st.caption(
        f"What should {ACTIVE_MUNICIPALITY.name} fund first? Rank reflects "
        "the selected strategy, current risk score, and available budget."
    )
    roads = results["roads"]
    if roads.empty:
        st.info("No projects fit within this scenario's budget.")
        return

    table = roads[[
        "Priority Rank", "Road Name", "PCI", "Risk Score", "Treatment",
        "Estimated Cost", "Risk Reason",
    ]].rename(columns={
        "Priority Rank": "Rank",
        "Road Name": "Road",
        "Estimated Cost": "Cost",
        "Risk Score": "Risk",
        "Risk Reason": "Why Paventra selected it",
    })
    st.dataframe(
        table.style.format({"Cost": "${:,.0f}", "PCI": "{:.0f}", "Risk": "{:.0f}"}),
        use_container_width=True,
        hide_index=True,
    )
    st.divider()
