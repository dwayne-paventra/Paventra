from __future__ import annotations

import streamlit as st
import pandas as pd

from helpers.optimizer_helpers import optimize_budget


def render_optimizer_panel(
    roads: pd.DataFrame,
) -> None:

    st.divider()

    st.subheader("🧠 Budget Optimizer")

    st.caption(
        "Find the best combination of roads within a fixed budget."
    )

    budget = st.number_input(
        "Available Budget ($)",
        min_value=100000,
        max_value=50000000,
        value=5000000,
        step=500000,
    )

    results = optimize_budget(
        roads,
        budget,
    )

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "Roads Selected",
            len(results["roads"]),
        )

        st.metric(
            "Money Spent",
            f"${results['spent']:,.0f}",
        )

    with col2:

        st.metric(
            "Budget Remaining",
            f"${results['remaining']:,.0f}",
        )

        st.metric(
            "Average Risk",
            f"{results['network_risk']:.1f}",
        )

    st.markdown("### Recommended Roads")

    if results["roads"].empty:

        st.warning("No roads fit within this budget.")

    else:

        st.dataframe(
            results["roads"][
                [
                    "Road Name",
                    "Treatment",
                    "Estimated Cost",
                    "Risk Score",
                ]
            ],
            use_container_width=True,
        )