"""
AI Maintenance Advisor component.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from helpers.ai_helpers import get_ai_recommendation


def render_ai_panel(road: pd.Series) -> None:
    """
    Render the AI maintenance recommendation panel.
    """

    st.subheader("🤖 AI Maintenance Advisor")

    risk = road["Risk Level"]
    condition = road["Condition"]
    traffic = road["Traffic"]

    st.info(get_ai_recommendation(risk))

    st.markdown("### 📊 AI Analysis")

    st.write(
        f"""
The selected road is **{condition}** with **{traffic}** traffic
and has a **{risk}** risk rating.

Based on these conditions, Paventra recommends the maintenance
strategy shown above to maximize pavement life while minimizing
future repair costs.
"""
    )

    st.markdown("---")