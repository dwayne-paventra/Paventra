"""
Network Map component.
"""

from __future__ import annotations

import streamlit as st
from streamlit_folium import st_folium

from helpers.map_helpers import create_network_map


def render_network_map(
    roads,
    selected_ids=None,
):
    """
    Render the interactive Michigan road network.
    """

    st.subheader("🗺️ Michigan Road Network")

    st.caption(
        "Explore the transportation network by interacting with the map."
    )

    road_map = create_network_map(
        roads,
        selected_ids,
    )

    st_folium(
        road_map,
        width=None,
        height=700,
        returned_objects=[],
    )

    st.divider()