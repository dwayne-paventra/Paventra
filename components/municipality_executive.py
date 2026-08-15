"""Executive overview for any configured public agency."""

from __future__ import annotations

import streamlit as st

from components.municipality_presentation import summarize_network_for_presentation
from pilot.municipality_config import MunicipalityConfig


def render_municipality_executive_overview(
    config: MunicipalityConfig,
    roads,
    results: dict | None = None,
) -> None:
    """Render an executive briefing, intentionally free of engineering jargon."""

    summary = summarize_network_for_presentation(roads, results)
    provenance = config.data_provenance

    st.title(config.pilot_name)
    st.caption(
        f"{config.formal_name} · {provenance.analysis_label} · "
        f"{summary.segment_count} segments / {summary.total_lane_miles:.1f} lane miles"
    )
    st.markdown(
        f'<div class="pilot-notice">{config.pilot_disclaimer}</div>',
        unsafe_allow_html=True,
    )
    st.markdown("### Executive summary")
    metrics = st.columns(4)
    metrics[0].metric("Network Health", f"{summary.network_health:.0f}/100")
    metrics[1].metric("Average PCI", f"{summary.average_pci:.0f}")
    metrics[2].metric("High-Risk Segments", summary.high_risk_segments)
    metrics[3].metric(
        "Estimated Investment Need",
        f"${summary.estimated_investment_need / 1_000_000:.2f}M",
    )

    strategy, action = st.columns(2)
    with strategy.container(border=True):
        st.markdown("**Current investment strategy**")
        if summary.strategy_name is None:
            st.write("Choose a strategy in Pavement Analytics.")
        else:
            st.markdown(f"#### {summary.strategy_name}")
            st.caption(
                f"Planning budget: ${summary.strategy_budget:,.0f} · "
                f"{results['selected_lane_miles']:.1f} treatable lane miles"
            )
    with action.container(border=True):
        st.markdown("**Recommended next action**")
        if summary.next_road is None:
            st.write("Review strategy assumptions and available funding.")
        else:
            st.markdown(f"#### Review {summary.next_road}")
            st.caption(
                f"Priority treatment: {summary.next_treatment} · "
                f"Planning cost: ${summary.next_cost:,.0f}"
            )
    st.divider()
