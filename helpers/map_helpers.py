"""
Map helper functions for Paventra.
"""

from __future__ import annotations

import folium
import pandas as pd
from folium.plugins import MarkerCluster


def risk_color(score: float) -> str:
    """Return marker color based on risk score."""

    if score >= 80:
        return "red"
    elif score >= 60:
        return "orange"
    elif score >= 40:
        return "blue"
    else:
        return "green"


def create_network_map(roads: pd.DataFrame):
    """Create an interactive Folium road network map."""

    if roads.empty:
        return folium.Map(
            location=[42.33, -83.05],
            zoom_start=10,
        )

    center_lat = roads["Latitude"].mean()
    center_lon = roads["Longitude"].mean()

    road_map = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=11,
        tiles="CartoDB Positron",
        control_scale=True,
    )

    cluster = MarkerCluster().add_to(road_map)

    for _, road in roads.iterrows():

        color = risk_color(road["Risk Score"])

        popup = f"""
        <div style="width:260px">

        <h3 style="margin-bottom:10px;">
        🛣️ {road["Road Name"]}
        </h3>

        <hr>

        <b>Condition</b><br>
        {road["Condition"]}

        <br><br>

        <b>Risk Level</b><br>
        {road["Risk Level"]}

        <br><br>

        <b>Risk Score</b><br>
        {road["Risk Score"]}

        <br><br>

        <b>Recommended Treatment</b><br>
        {road["Treatment"]}

        <br><br>

        <b>Traffic Level</b><br>
        {road["Traffic"]}

        <br><br>

        <b>Average Daily Traffic (ADT)</b><br>
        {road["ADT"]:,}

        <br><br>

        <b>Surface Type</b><br>
        {road["Surface Type"]}

        <br><br>

        <b>Speed Limit</b><br>
        {road["Speed Limit"]} mph

        <br><br>

        <b>Road Length</b><br>
        {road["Road Length"]} miles

        </div>
        """

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
            popup=folium.Popup(
                folium.Html(popup, script=True),
                max_width=300,
            ),
        ).add_to(cluster)

    return road_map