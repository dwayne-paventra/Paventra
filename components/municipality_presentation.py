"""Shared presentation helpers for municipality-facing application screens."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

import streamlit as st

from pilot.municipality_config import MunicipalityConfig


@dataclass(frozen=True)
class NetworkPresentationSummary:
    """Validated inventory and scenario values used in executive presentation."""

    average_pci: float
    network_health: float
    high_risk_segments: int
    high_risk_lane_miles: float
    estimated_investment_need: float
    total_lane_miles: float
    segment_count: int
    strategy_name: str | None
    strategy_budget: float | None
    next_road: str | None
    next_treatment: str | None
    next_cost: float | None


def summarize_network_for_presentation(
    roads,
    results: dict | None,
) -> NetworkPresentationSummary:
    """Return presentation values without introducing new analytical rules."""

    if roads.empty:
        average_pci = network_health = high_risk_lane_miles = 0.0
        high_risk_segments = segment_count = 0
        estimated_investment_need = total_lane_miles = 0.0
    else:
        average_pci = float(roads["PCI"].mean())
        network_health = max(0.0, 100.0 - float(roads["Risk Score"].mean()))
        high_risk_mask = roads["Risk Level"] == "High"
        high_risk_segments = int(high_risk_mask.sum())
        high_risk_lane_miles = float(roads.loc[high_risk_mask, "Lane Miles"].sum())
        estimated_investment_need = float(roads["Estimated Cost"].sum())
        total_lane_miles = float(roads["Lane Miles"].sum())
        segment_count = int(len(roads))

    selected = results["roads"] if results is not None else roads.iloc[0:0]
    if selected.empty:
        next_road = next_treatment = None
        next_cost = None
    else:
        first = selected.iloc[0]
        next_road = str(first["Road Name"])
        next_treatment = str(first["Treatment"])
        next_cost = float(first["Estimated Cost"])

    return NetworkPresentationSummary(
        average_pci=average_pci,
        network_health=network_health,
        high_risk_segments=high_risk_segments,
        high_risk_lane_miles=high_risk_lane_miles,
        estimated_investment_need=estimated_investment_need,
        total_lane_miles=total_lane_miles,
        segment_count=segment_count,
        strategy_name=str(results["scenario_name"]) if results is not None else None,
        strategy_budget=(
            float(results["scenario"]["budget"])
            if results is not None
            else None
        ),
        next_road=next_road,
        next_treatment=next_treatment,
        next_cost=next_cost,
    )


def render_municipality_section_header(
    config: MunicipalityConfig,
    section_name: str,
    description: str,
) -> None:
    """Give every analysis destination a consistent municipality identity."""

    provenance = config.data_provenance
    st.caption(config.pilot_name)
    st.title(section_name)
    st.markdown(
        f'<span class="paventra-status-chip">{escape(provenance.label)} data</span>',
        unsafe_allow_html=True,
    )
    st.caption(f"{config.formal_name} · {description}")
    if config.normalized_data_status == "illustrative":
        st.caption(config.pilot_disclaimer)


def render_network_snapshot(summary: NetworkPresentationSummary) -> None:
    """Render a compact current-network step for the analytics workflow."""

    st.subheader("1. Current network")
    st.caption(
        "Inventory values and Paventra's transparent risk calculation establish the "
        "current planning baseline."
    )
    columns = st.columns(4)
    columns[0].metric("Average PCI", f"{summary.average_pci:.0f}")
    columns[1].metric("Network Health", f"{summary.network_health:.0f}/100")
    columns[2].metric("High-Risk Segments", summary.high_risk_segments)
    columns[3].metric("High-Risk Lane Miles", f"{summary.high_risk_lane_miles:.1f}")
    st.markdown('<div class="paventra-workflow-arrow">↓</div>', unsafe_allow_html=True)
