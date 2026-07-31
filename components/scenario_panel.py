import streamlit as st
from helpers.scenario_helpers import calculate_high_risk_program


def render_scenario_panel(roads):

    st.subheader("🤖 AI Scenario Planner")

    st.caption(
        "Simulate the impact of repairing every High Risk road."
    )

    scenario = calculate_high_risk_program(roads)

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "High Risk Roads",
            scenario["road_count"],
        )

        st.metric(
            "Lane Miles",
            f"{scenario['lane_miles']:.1f}",
        )

    with col2:
        st.metric(
            "Estimated Cost",
            f"${scenario['total_cost']:,.0f}",
        )

        st.metric(
            "Average Risk",
            f"{scenario['average_risk_before']:.1f}",
        )

    st.info(
        f"AI Recommendation: Repair the {scenario['road_count']} highest-risk roads first "
        f"for an estimated investment of ${scenario['total_cost']:,.0f}."
    )