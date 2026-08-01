"""
AI Executive Summary component.
"""

from __future__ import annotations

import streamlit as st


def render_ai_summary(results: dict):

    roads = results["roads"]

    if roads.empty:

        st.info(
            "No roads were selected within the current budget."
        )

        return

    total_roads = len(roads)

    spent = results["spent"]

    remaining = results["remaining"]

    average_risk = results["network_risk"]

    utilization = spent / (spent + remaining) * 100

    highest_risk = roads["Risk Score"].max()

    st.subheader("🤖 AI Recommendation Summary")

    st.success(

        f"""
Paventra recommends treating **{total_roads} roads**
within the available budget.

This recommendation prioritizes roads with the
highest network risk while maximizing the value
of every maintenance dollar.

• **Budget Utilized:** {utilization:.1f}%

• **Average Risk of Selected Roads:** {average_risk:.1f}

• **Highest Selected Risk Score:** {highest_risk}

• **Remaining Budget:** ${remaining:,.0f}

Overall, this investment strategy provides the
greatest reduction in network risk while staying
within the available funding.
        """
    )

    st.divider()