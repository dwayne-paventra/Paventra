"""
Basemap management for Paventra GIS.
"""

from __future__ import annotations

import folium

def add_basemaps(road_map):
    """
    Add all supported basemaps.
    """

    folium.TileLayer(
        "OpenStreetMap",
        name="OpenStreetMap",
        overlay=False,
        control=True,
    ).add_to(road_map)

    folium.TileLayer(
        "CartoDB Positron",
        name="Light",
        overlay=False,
        control=True,
    ).add_to(road_map)

    folium.TileLayer(
        "CartoDB Dark_Matter",
        name="Dark",
        overlay=False,
        control=True,
    ).add_to(road_map)

    folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri",
    name="Esri Satellite",
    overlay=False,
    control=True,
).add_to(road_map)

    folium.TileLayer(
    tiles="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
    attr="© OpenTopoMap contributors",
    name="OpenTopoMap",
    overlay=False,
    control=True,
).add_to(road_map)

    folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
    attr="Esri",
    name="Esri Topographic",
    overlay=False,
    control=True,
).add_to(road_map)
    
    