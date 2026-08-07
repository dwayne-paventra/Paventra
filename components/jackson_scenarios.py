"""Scenario selector and executive outcome display for the Jackson Pilot."""

from __future__ import annotations

import streamlit as st

from pilot.jackson_scenarios import JACKSON_SCENARIOS


def render_jackson_scenario_selector() -> str:
    st.subheader("4. Budget scenario")
    scenario_name = st.radio(
        "Choose an illustrative investment strategy",
        list(JACKSON_SCENARIOS),
        index=list(JACKSON_SCENARIOS).index(
            st.session_state.get("jackson_scenario", "Balanced Annual Program")
        ),
        key="jackson_scenario",
        horizontal=True,
    )
    scenario = JACKSON_SCENARIOS[scenario_name]
    st.caption(scenario["description"])
    return scenario_name


def render_jackson_scenario_impact(results: dict) -> None:
    st.subheader(results["scenario_name"])
    st.caption("Planning estimate based on the current illustrative records and selected projects.")
    metrics = [
        ("Budget", f"${results['scenario']['budget']:,.0f}"),
        ("Projects", len(results["roads"])),
        ("Total Investment", f"${results['spent'] / 1_000_000:.1f}M"),
        ("Estimated Risk Change", f"{results['risk_reduction_percent']:.0f}%"),
        ("Portfolio Risk", f"{results['network_risk_before']:.0f} to {results['network_risk_after']:.0f}"),
    ]
    for column, (label, value) in zip(st.columns(3), metrics[:3]):
        column.metric(label, value)
    for column, (label, value) in zip(st.columns(2), metrics[3:]):
        column.metric(label, value)
    st.divider()
