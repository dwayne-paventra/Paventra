"""
Marker rendering for Paventra GIS.
"""

from __future__ import annotations

import folium
import pandas as pd

from gis.styles import risk_color


def add_standard_marker(cluster, road, popup):
    """Render a standard road marker."""

    color = risk_color(road["Risk Score"])

    folium.CircleMarker(
        location=[
            road["Latitude"],
            road["Longitude"],
        ],
        radius=8,
        color=color,
        fill=True,
        fill_color=color,
        fill_opacity=0.9,
        weight=2,
        popup=folium.Popup(
            folium.Html(popup, script=True),
            max_width=300,
        ),
    ).add_to(cluster)

def add_priority_marker(cluster, road, popup):
    """Render a scenario-funded priority road marker."""

    color = risk_color(road["Risk Score"])

    folium.CircleMarker(
        location=[
            road["Latitude"],
            road["Longitude"],
        ],
        radius=13,
        color=color,
        weight=4,
        fill=False,
    ).add_to(cluster)

    folium.Marker(
        location=[
            road["Latitude"],
            road["Longitude"],
        ],
        popup=folium.Popup(
            folium.Html(popup, script=True),
            max_width=300,
        ),
        icon=folium.Icon(
            icon="star",
            prefix="fa",
            color="orange",
        ),
    ).add_to(cluster)


# Compatibility alias for older GIS callers. The active UI uses neutral wording.
add_ai_marker = add_priority_marker
