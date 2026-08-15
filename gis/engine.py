"""
Core GIS engine for Paventra.
"""

from __future__ import annotations

import folium
import pandas as pd
from folium.plugins import MarkerCluster

from gis.basemaps import add_basemaps
from gis.geometry_manager import GeometryManager
from gis.legend import add_legend
from gis.markers import (
    add_priority_marker,
    add_standard_marker,
)
from gis.popups import build_popup


GEOMETRY_PATH = (
    "data/geometry/michigan/roads/gis_osm_roads_free_1.shp"
)


def create_network_map(
    roads: pd.DataFrame,
    selected_ids=None,
    center_on=None,
    show_geometry=False,
    map_center=None,
    zoom_start=11,
):
    """
    Create the Paventra interactive GIS map.
    """

    # -------------------------------------------------
    # Empty dataset
    # -------------------------------------------------

    if roads.empty:

        return folium.Map(
            location=[42.33, -83.05],
            zoom_start=10,
        )

    # -------------------------------------------------
    # Determine map center
    # -------------------------------------------------

    if center_on is not None:

        center_lat = center_on["Latitude"]
        center_lon = center_on["Longitude"]

    elif map_center is not None:
        center_lat, center_lon = map_center
    else:

        center_lat = roads["Latitude"].mean()
        center_lon = roads["Longitude"].mean()

    # -------------------------------------------------
    # Create map
    # -------------------------------------------------

    road_map = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom_start,
        tiles=None,
        control_scale=True,
    )

    add_basemaps(
        road_map
    )

    # -------------------------------------------------
    # Create Feature Groups
    # -------------------------------------------------

    road_layer = folium.FeatureGroup(
        name="Road Network",
        show=True,
    )

    priority_layer = folium.FeatureGroup(
        name="Priority Projects",
        show=True,
    )

    geometry_layer = folium.FeatureGroup(
        name="Selected Road",
        show=True,
    )

    road_cluster = MarkerCluster().add_to(
        road_layer
    )

    priority_cluster = MarkerCluster().add_to(
        priority_layer
    )

    # -------------------------------------------------
    # Marker selection lookup
    # -------------------------------------------------

    selected_lookup = {
        str(x).strip()
        for x in (selected_ids or [])
    }

    # -------------------------------------------------
    # Render Markers
    # -------------------------------------------------

    for _, road in roads.iterrows():

        popup = build_popup(
            road
        )

        road_id = str(
            road["Road ID"]
        ).strip()

        if road_id in selected_lookup:

            add_priority_marker(
                priority_cluster,
                road,
                popup,
            )

        else:

            add_standard_marker(
                road_cluster,
                road,
                popup,
            )

    # -------------------------------------------------
    # Selected Road Geometry
    # -------------------------------------------------

    if show_geometry and center_on is not None:

        manager = GeometryManager()

        segments = manager.find_entire_road(
            GEOMETRY_PATH,
            latitude=center_on["Latitude"],
            longitude=center_on["Longitude"],
        )

        if segments is not None and not segments.empty:

            # Zoom to the selected roadway

            minx, miny, maxx, maxy = (
                segments.total_bounds
            )

            road_map.fit_bounds(
                [
                    [miny, minx],
                    [maxy, maxx],
                ]
            )

            # Draw the entire roadway

            folium.GeoJson(
                data=segments,
                style_function=lambda feature: {
                    "color": "#0066FF",
                    "weight": 6,
                    "opacity": 0.95,
                },
                highlight_function=lambda feature: {
                    "color": "#00AAFF",
                    "weight": 8,
                    "opacity": 1.0,
                },
            ).add_to(
                geometry_layer
            )

    # -------------------------------------------------
    # Add Layers
    # -------------------------------------------------

    road_layer.add_to(
        road_map
    )

    priority_layer.add_to(
        road_map
    )

    if show_geometry and center_on is not None:

        geometry_layer.add_to(
            road_map
        )

    # -------------------------------------------------
    # Layer Control
    # -------------------------------------------------

    folium.LayerControl(
        collapsed=False,
    ).add_to(
        road_map
    )

    # -------------------------------------------------
    # Legend
    # -------------------------------------------------

    add_legend(
        road_map
    )

    # -------------------------------------------------
    # Finished
    # -------------------------------------------------

    return road_map
