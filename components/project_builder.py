"""
Project Builder for Paventra.
"""

from __future__ import annotations

import streamlit as st


def initialize_project():

    if "project_roads" not in st.session_state:

        st.session_state.project_roads = []


def add_road(road):

    road_id = str(road["Road ID"])

    existing = [
        str(r["Road ID"])
        for r in st.session_state.project_roads
    ]

    if road_id not in existing:

        st.session_state.project_roads.append(
            road.to_dict()
        )


def remove_road(road_id):

    st.session_state.project_roads = [

        road

        for road in st.session_state.project_roads

        if str(road["Road ID"]) != str(road_id)

    ]


def render_project_panel():

    initialize_project()

    st.subheader("🚧 Current Project")

    if len(st.session_state.project_roads) == 0:

        st.info("No roads added.")

        return

    total_cost = 0
    total_lane_miles = 0
    total_risk = 0
    total_condition = 0

    for road in st.session_state.project_roads:

        st.write(f"**{road['Road Name']}**")

        col1, col2 = st.columns([4,1])

        with col2:

            if st.button(
                "❌",
                key=f"remove_{road['Road ID']}"
            ):

                remove_road(
                    road["Road ID"]
                )

                st.rerun()

        total_cost += road["Estimated Cost"]
        total_lane_miles += road["Lane Miles"]
        total_risk += road["Risk Score"]
        total_condition += road["Condition"]

    count = len(st.session_state.project_roads)

    st.divider()

    st.metric(
        "Roads",
        count,
    )

    st.metric(
        "Lane Miles",
        round(total_lane_miles,2),
    )

    st.metric(
        "Average Risk",
        round(total_risk/count,1),
    )

    st.metric(
        "Average Condition",
        round(total_condition/count,1),
    )

    st.metric(
        "Estimated Cost",
        f"${total_cost:,.0f}",
    )

    st.divider()

    st.button(
        "💾 Save Project",
        disabled=True,
    )

    st.button(
        "📄 Export PDF",
        disabled=True,
    )

    st.button(
        "📊 Export CSV",
        disabled=True,
    )