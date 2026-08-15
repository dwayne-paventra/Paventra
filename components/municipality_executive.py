"""Executive overview for any configured public agency."""

from __future__ import annotations

import streamlit as st

from pilot.municipality_config import MunicipalityConfig


def render_municipality_executive_overview(
    config: MunicipalityConfig,
    roads,
    results: dict | None = None,
) -> None:
    """Render an executive briefing, intentionally free of engineering jargon."""

    average_pci = float(roads["PCI"].mean()) if not roads.empty else 0.0
    high_risk = int((roads["Risk Level"] == "High").sum()) if not roads.empty else 0
    high_risk_lane_miles = float(
        roads.loc[roads["Risk Level"] == "High", "Lane Miles"].sum()
    ) if not roads.empty else 0.0
    demonstration_need = float(roads["Estimated Cost"].sum()) if not roads.empty else 0.0
    annual_investment = float(results["scenario"]["budget"]) if results else 3_000_000.0
    provenance = config.data_provenance

    st.title(config.pilot_name)
    st.caption(f"{provenance.analysis_label} | A decision briefing for pavement investment planning")
    st.markdown(
        f'<div class="pilot-notice">{config.pilot_disclaimer}</div>',
        unsafe_allow_html=True,
    )
    st.markdown("### 1. Network condition")
    condition, exposure, action = st.columns(3)
    condition.markdown(f"**Condition**  \nAverage pavement condition is **PCI {average_pci:.0f}**.")
    exposure.markdown(
        f"**Exposure**  \n**{high_risk}** high-risk segments represent **{high_risk_lane_miles:.1f}** lane miles."
    )
    action.markdown(
        f"**Action**  \nThe selected strategy directs up to **${annual_investment:,.0f}** toward the current priorities."
    )

    values = [
        ("Network Health", f"{max(0, 100 - roads['Risk Score'].mean()):.0f}/100"),
        ("Average PCI", f"{average_pci:.0f}"),
        ("High-Risk Segments", f"{high_risk}"),
        ("Estimated Investment Need", f"${demonstration_need:,.0f}"),
        ("Treatable Lane Miles", f"{results['selected_lane_miles']:.1f}" if results else "Select scenario"),
    ]
    for column, (label, value) in zip(st.columns(3), values[:3]):
        column.metric(label, value)
    for column, (label, value) in zip(st.columns(2), values[3:]):
        column.metric(label, value)
    st.divider()
