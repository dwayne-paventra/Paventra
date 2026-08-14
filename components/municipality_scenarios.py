"""Scenario selection and impact display for any configured public agency."""

from __future__ import annotations

from collections.abc import Mapping

import streamlit as st


def render_municipality_scenario_selector(
    scenarios: Mapping[str, dict],
    session_key: str = "municipality_scenario",
) -> str:
    st.subheader("4. Budget scenario")
    scenario_names = list(scenarios)
    default_scenario = "Balanced Annual Program"
    selected_scenario = st.session_state.get(session_key, default_scenario)
    if selected_scenario not in scenarios:
        selected_scenario = default_scenario if default_scenario in scenarios else scenario_names[0]
    scenario_name = st.radio(
        "Choose an illustrative investment strategy",
        scenario_names,
        index=scenario_names.index(selected_scenario),
        key=session_key,
        horizontal=True,
    )
    st.caption(scenarios[scenario_name]["description"])
    return scenario_name


def render_municipality_scenario_impact(results: dict) -> None:
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
