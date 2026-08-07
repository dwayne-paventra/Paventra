"""
Road geometry utilities for Paventra.
"""

from __future__ import annotations

import geopandas as gpd


def load_road_geometry(path: str):
    """
    Load a road geometry dataset.
    """

    return gpd.read_file(path)