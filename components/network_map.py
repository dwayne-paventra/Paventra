"""
Network Map component.
"""

from __future__ import annotations

import streamlit as st
from streamlit_folium import st_folium

from gis.engine import create_network_map
from components.project_builder import (
    add_road,
    render_project_panel,
)

print("LOADED:", __file__)

def render_network_map(
    roads,
    selected_ids=None,
    center_on=None,
    show_geometry=False,
):
    """
    Render the interactive Michigan road network.
    """

    st.subheader("🗺️ Michigan Road Network")

    st.error("NETWORK_MAP VERSION 2")

    st.caption(
        "Explore the transportation network by interacting with the map."
    )

    # ------------------------------------------------
    # Road Search
    # ------------------------------------------------

    search_text = st.text_input(
        "🔍 Search Roads",
        placeholder="Search by Road ID or Road Name...",
    )

    matching_roads = roads

    if search_text:

        matching_roads = roads[
            roads["Road Name"]
                .str.contains(search_text, case=False, na=False)
            |
            roads["Road ID"]
                .astype(str)
                .str.contains(search_text, case=False, na=False)
        ]

    selected_search = None

    if search_text:

        if matching_roads.empty:

            st.warning("No matching roads found.")

        else:

            selected_search = st.selectbox(
                "Matching Roads",
                matching_roads["Road Name"].tolist(),
            )
        st.write("DEBUG")
        st.write("search_text =", search_text)
        st.write("selected_search =", selected_search)
        st.write("matching roads =", len(matching_roads))

    selected_search_id = None

    if selected_search:

        st.write("Inside selected_search block")

        selected_row = matching_roads[
            matching_roads["Road Name"] == selected_search
        ].iloc[0]

        selected_search_id = [
            str(selected_row["Road ID"])
        ]

        center_on = selected_row
        show_geometry = True

        st.success(
            f"Selected: {selected_row['Road Name']}"
        )

        if st.button(
            "➕ Add Selected Road",
            use_container_width=True,
        ):

            add_road(
                selected_row
            )

            st.success(
                "Road added to project."
            )

    # ------------------------------------------------
    # Interactive Map
    # ------------------------------------------------

    active_selection = selected_ids

    if selected_search_id:

        active_selection = selected_search_id

    road_map = create_network_map(
        roads,
        active_selection,
        center_on=center_on,
        show_geometry=show_geometry,
    )

    import time

    t = time.perf_counter()

    st_folium(
        road_map,
        width=None,
        height=700,
        returned_objects=[],
    )

    st.write(
        "st_folium:",
        round(time.perf_counter() - t, 2),
        "seconds"
    )

    st.divider()
