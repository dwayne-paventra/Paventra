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


def create_network_map(
    roads: pd.DataFrame,
    selected_ids=None,
):
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

    # Convert selected IDs to strings for comparison
    selected_lookup = {
        str(x).strip()
        for x in (selected_ids or [])
    }

    for _, road in roads.iterrows():

        road_id = str(road["Road ID"]).strip()

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

        # -----------------------------
        # AI Recommended Roads
        # -----------------------------
        if road_id in selected_lookup:

            # Colored halo showing the road's risk
            folium.CircleMarker(
                location=[
                    road["Latitude"],
                    road["Longitude"],
                ],
                radius=13,
                color=risk_color(
                    road["Risk Score"]
                ),
                weight=4,
                fill=False,
            ).add_to(cluster)

            # Gold star
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

        # -----------------------------
        # Normal Roads
        # -----------------------------
        else:

            color = risk_color(
                road["Risk Score"]
            )

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

    legend = """
    <div style="
    position: fixed;
    bottom: 40px;
    left: 40px;
    width: 230px;
    background:white;
    border:2px solid grey;
    border-radius:10px;
    padding:12px;
    z-index:9999;
    font-size:14px;
    box-shadow:2px 2px 8px rgba(0,0,0,.3);
    ">

    <b>Paventra Legend</b>

    <hr>

    <span style="color:red;">●</span> High Risk<br>
    <span style="color:orange;">●</span> Medium Risk<br>
    <span style="color:blue;">●</span> Moderate Risk<br>
    <span style="color:green;">●</span> Low Risk<br><br>

    ⭐ AI Recommended Road

    </div>
    """

    road_map.get_root().html.add_child(
        folium.Element(legend)
    )

    return road_map