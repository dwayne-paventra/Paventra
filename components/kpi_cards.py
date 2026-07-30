import streamlit as st
from utils import metric_card


def render_kpi_cards(metrics):
    """
    Display the four executive KPI cards.
    """

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        metric_card(
            "🛣 Roads Analyzed",
            f"{metrics['roads_total']:,}",
            "#1565C0",
        )

    with c2:
        metric_card(
            "⚠ Average Risk",
            f"{metrics['avg_risk']:.1f}",
            "#F9A825",
        )

    with c3:
        metric_card(
            "🔴 High Risk Roads",
            f"{metrics['high_risk']:,}",
            "#D32F2F",
        )

    with c4:
        metric_card(
            "🟢 Low Risk Roads",
            f"{metrics['low_risk']:,}",
            "#2E7D32",
        )

    st.markdown("---")