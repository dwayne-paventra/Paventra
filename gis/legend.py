"""
Legend rendering for Paventra GIS.
"""

from __future__ import annotations

import folium


def add_legend(road_map):
    """
    Add the Paventra legend to the map.
    """

    legend = """
    ...
    """

    road_map.get_root().html.add_child(
        folium.Element(legend)
    )