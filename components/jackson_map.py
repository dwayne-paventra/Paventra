"""Jackson Pilot map explorer built on the existing Folium map engine."""

from __future__ import annotations

import streamlit as st
from streamlit_folium import st_folium

from gis.engine import create_network_map
from pilot.jackson_config import JACKSON_MAP_CENTER, JACKSON_MAP_ZOOM


def render_jackson_map(roads, results: dict) -> None:
    st.subheader("2. Risk and network map")
    st.caption("Colored markers show current risk. Starred markers are priority investment recommendations.")

    road_names = roads["Road Name"].tolist()
    selected_name = st.selectbox("Select a road to review", road_names, key="jackson_road_selection")
    selected_road = roads.loc[roads["Road Name"] == selected_name].iloc[0]
    selected_ids = set(results["selected_ids"])
    selected_ids.add(str(selected_road["Road ID"]))

    map_roads = roads.copy()
    rank_lookup = results["roads"].set_index("Road ID")["Priority Rank"].to_dict() if not results["roads"].empty else {}
    map_roads["Priority Rank"] = map_roads["Road ID"].map(rank_lookup)
    try:
        road_map = create_network_map(
            map_roads,
            selected_ids=selected_ids,
            map_center=JACKSON_MAP_CENTER,
            zoom_start=JACKSON_MAP_ZOOM,
        )
        st_folium(road_map, width=None, height=560, returned_objects=[])
    except Exception:
        st.warning(
            "Map imagery is unavailable. The selected-road details and investment recommendations remain available for this review."
        )

    st.markdown("#### Selected road")
    detail_columns = st.columns(2)
    detail_columns[0].metric("PCI", f"{selected_road['PCI']:.0f}")
    detail_columns[1].metric("Risk score", f"{selected_road['Risk Score']:.0f}")
    detail_columns = st.columns(2)
    detail_columns[0].metric("Recommended treatment", selected_road["Treatment"])
    detail_columns[1].metric("Estimated cost", f"${selected_road['Estimated Cost']:,.0f}")
    st.info(f"Why it is a priority: {selected_road['Risk Reason']}")
    st.divider()
