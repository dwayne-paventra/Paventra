"""Network map explorer for any configured public agency."""

from __future__ import annotations

import streamlit as st
from streamlit_folium import st_folium

from gis.engine import create_network_map
from pilot.municipality_config import MunicipalityConfig
from pilot.municipality_spatial import load_spatial_artifact


def render_municipality_map(
    config: MunicipalityConfig,
    roads,
    results: dict,
    selection_key: str = "municipality_road_selection",
) -> None:
    st.subheader("2. Risk and network map")
    st.caption(
        f"{len(roads)} inventory segments centered on {config.short_name}. "
        "Road color shows calculated risk; highlighted roads are projects funded by the selected strategy."
    )
    if config.normalized_data_status == "illustrative":
        st.info(
            "Illustrative map: road records and coordinates are demonstration inputs, "
            "not an official agency GIS inventory."
        )

    road_positions = list(range(len(roads)))

    def road_label(position: int) -> str:
        road = roads.iloc[position]
        limits = [str(road.get(field, "")).strip() for field in ("from_street", "to_street")]
        limits = [value for value in limits if value and value.lower() != "nan"]
        suffix = f" · {' to '.join(limits)}" if limits else f" · Segment {road['Road ID']}"
        return f"{road['Road Name']}{suffix}"

    selected_position = st.selectbox(
        "Select a road to review",
        road_positions,
        format_func=road_label,
        key=selection_key,
    )
    selected_road = roads.iloc[int(selected_position)]
    selected_ids = set(results["selected_ids"])

    map_roads = roads.copy()
    rank_lookup = results["roads"].set_index("Road ID")["Priority Rank"].to_dict() if not results["roads"].empty else {}
    map_roads["Priority Rank"] = map_roads["Road ID"].map(rank_lookup)
    try:
        road_map = create_network_map(
            map_roads,
            selected_ids=selected_ids,
            map_center=config.map_center,
            zoom_start=config.map_zoom,
            road_geometry=load_spatial_artifact(config.data_directory),
        )
        st_folium(road_map, width=None, height=560, returned_objects=[])
    except Exception:
        st.warning(
            "Map imagery is unavailable. The selected-road details and investment recommendations remain available for this review."
        )

    with st.container(border=True):
        st.markdown(f"#### {selected_road['Road Name']}")
        st.caption(
            f"Segment {selected_road.get('segment_id', selected_road['Road ID'])} · "
            f"{selected_road['Lane Miles']:.1f} lane miles · "
            f"{selected_road['Traffic']} traffic"
        )
        detail_columns = st.columns(4)
        detail_columns[0].metric("PCI", f"{selected_road['PCI']:.0f}")
        detail_columns[1].metric("Calculated Risk", f"{selected_road['Risk Score']:.0f}")
        detail_columns[2].metric("Treatment", selected_road["Treatment"])
        detail_columns[3].metric("Planning Cost", f"${selected_road['Estimated Cost']:,.0f}")
        st.info(f"Priority factors: {selected_road['Risk Reason']}")
    st.divider()
