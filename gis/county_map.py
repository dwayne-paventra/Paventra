"""
County heat map for Paventra.
"""

from __future__ import annotations

from pathlib import Path

import folium
import geopandas as gpd


PROJECT_ROOT = Path(__file__).resolve().parent.parent

COUNTY_SHP = (
    PROJECT_ROOT
    / "data"
    / "geometry"
    / "michigan"
    / "county"
    / "county.shp"
)


def build_county_heatmap(
    summary,
    metric="Average_Risk",
):

    counties = gpd.read_file(COUNTY_SHP)

    counties = counties.merge(
        summary,
        left_on="Name",
        right_on="County",
        how="left",
    )

    county_map = folium.Map(
        location=[44.5, -85.5],
        zoom_start=7,
        tiles="CartoDB Positron",
    )

    folium.Choropleth(
        geo_data=counties,
        data=counties,
        columns=[
            "Name",
            metric,
        ],
        key_on="feature.properties.Name",
        fill_color="YlOrRd",
        fill_opacity=0.8,
        line_opacity=0.4,
        legend_name=metric.replace("_", " "),
        nan_fill_color="lightgray",
    ).add_to(county_map)

    folium.GeoJson(
        counties,
        tooltip=folium.GeoJsonTooltip(
            fields=[
                "Name",
                "Roads",
                "Average_Risk",
                "Average_Condition",
                "Average_ADT",
            ],
            aliases=[
                "County",
                "Roads",
                "Avg Risk",
                "Avg Condition",
                "Avg ADT",
            ],
            localize=True,
        ),
    ).add_to(county_map)

    return county_map