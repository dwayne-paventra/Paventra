"""
Road rendering utilities.
"""

from __future__ import annotations

import folium


def draw_geometry(
    road_map,
    geometry,
    layer,
):
    """
    Draw a selected road segment.

    Parameters
    ----------
    road_map : folium.Map
        The active map.

    geometry : shapely.geometry
        Road geometry to render.

    layer : folium.FeatureGroup
        FeatureGroup that owns all selected road geometry.
        This prevents individual segments from appearing
        in the LayerControl.
    """

    folium.GeoJson(
        data=geometry,
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
        tooltip=None,
        control=False,
        overlay=False,
        show=True,
    ).add_to(layer)