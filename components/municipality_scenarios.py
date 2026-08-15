"""Scenario selection and impact display for any configured public agency."""

from __future__ import annotations

from collections.abc import Mapping

import streamlit as st


def resolve_municipality_scenario_name(
    scenarios: Mapping[str, dict],
    selected_scenario: str | None = None,
) -> str:
    """Resolve a configured scenario without changing scenario definitions."""

    if not scenarios:
        raise ValueError("Scenario selection requires at least one configured scenario.")
    default_scenario = "Balanced Annual Program"
    if selected_scenario in scenarios:
        return str(selected_scenario)
    if default_scenario in scenarios:
        return default_scenario
    return next(iter(scenarios))


def render_municipality_scenario_selector(
    scenarios: Mapping[str, dict],
    session_key: str = "municipality_scenario",
    selection_state_key: str = "paventra_selected_scenario",
) -> str:
    st.subheader("2. Investment strategy")
    scenario_names = list(scenarios)
    selected_scenario = resolve_municipality_scenario_name(
        scenarios,
        st.session_state.get(session_key),
    )
    scenario_name = st.radio(
        "Choose an investment strategy",
        scenario_names,
        index=scenario_names.index(selected_scenario),
        key=session_key,
        horizontal=True,
    )
    # Widget state is removed when its page is no longer rendered. Keep the
    # selected application strategy available across Dashboard, Map, and Reports.
    st.session_state[selection_state_key] = scenario_name
    scenario = scenarios[scenario_name]
    st.caption(
        f"Scenario assumption · ${scenario['budget']:,.0f} planning budget · "
        f"{scenario['description']}"
    )
    st.markdown('<div class="paventra-workflow-arrow">↓</div>', unsafe_allow_html=True)
    return scenario_name


def render_municipality_scenario_impact(
    results: dict,
    analysis_label: str | None = None,
) -> None:
    st.subheader("4. Expected program impact")
    st.markdown(f"**{results['scenario_name']}**")
    basis = analysis_label or "Current configured inventory"
    st.caption(
        f"Calculated planning estimate based on {basis.lower()} and the selected projects; "
        "it is not a machine-learning prediction or engineering forecast."
    )
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
