"""Generic scenario UI with Jackson compatibility entry points."""

from __future__ import annotations

import streamlit as st

from pilot.jackson_scenarios import JACKSON_SCENARIOS
from pilot.municipality_scenarios import MUNICIPALITY_SCENARIOS


def render_municipality_scenario_selector(
    scenarios: dict = MUNICIPALITY_SCENARIOS,
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
    scenario = scenarios[scenario_name]
    st.caption(scenario["description"])
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


def render_jackson_scenario_selector() -> str:
    """Compatibility wrapper retaining the original scenarios and widget key."""

    return render_municipality_scenario_selector(
        JACKSON_SCENARIOS,
        session_key="jackson_scenario",
    )


def render_jackson_scenario_impact(results: dict) -> None:
    """Compatibility wrapper for the original impact renderer."""

    render_municipality_scenario_impact(results)
