from __future__ import annotations

import streamlit as st
import pandas as pd


def render_analytics_dashboard(roads: pd.DataFrame):

    st.subheader("📈 Network Analytics")

    col1, col2 = st.columns(2)

    with col1:

        st.markdown("#### Risk Distribution")

        risk_counts = (
            roads["Risk Level"]
            .value_counts()
            .sort_index()
        )

        st.bar_chart(risk_counts)

    with col2:

        st.markdown("#### Treatment Recommendations")

        treatment_counts = (
            roads["Treatment"]
            .value_counts()
        )

        st.bar_chart(treatment_counts)

    st.divider()