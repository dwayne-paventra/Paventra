"""
Road geometry search utilities.
"""

from __future__ import annotations

import geopandas as gpd


def find_geometry_by_name(
    roads: gpd.GeoDataFrame,
    road_name: str,
):
    """
    Return every geometry matching a road name.
    """

    if not road_name:
        return gpd.GeoDataFrame()

    matches = roads[
        roads["name"]
        .fillna("")
        .str.lower()
        == road_name.lower()
    ]

    return matches