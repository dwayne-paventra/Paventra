"""
Executive dashboard header for Paventra.
"""

import streamlit as st


def render_executive_dashboard(metrics: dict) -> None:
    """
    Render the executive dashboard summary.
    """

    st.title("🚧 Paventra")

    st.caption(
        "AI-Powered Pavement Asset Management Platform"
    )

    st.markdown("---")

    col1, col2 = st.columns([3, 1])

    with col1:

        st.markdown("### Executive Summary")

        st.write(
            f"""
The current pavement network contains **{metrics['roads_total']:,}**
road segments.

The average network risk score is
**{metrics['avg_risk']:.1f}**.

Overall Network Health is currently
**{metrics['network_health']:.1f}/100**
(**{metrics['health_status']}**).
"""
        )

    with col2:

        st.metric(
            "Network Health",
            f"{metrics['network_health']:.1f}",
        )

        st.metric(
            "High Risk Roads",
            metrics["high_risk"],
        )

    st.markdown("---")