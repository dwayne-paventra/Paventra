"""
Geometry manager for Paventra GIS.
"""

from __future__ import annotations

import geopandas as gpd

from gis.geometry import load_road_geometry
from gis.geometry_search import find_geometry_by_name


print("Loaded geometry_manager.py")


class GeometryManager:
    """
    Loads and manages statewide road geometry.
    """

    def __init__(self):
        self._roads = None


    def load(
        self,
        path: str,
    ) -> gpd.GeoDataFrame:

        if self._roads is None:
            self._roads = load_road_geometry(path)

        return self._roads



    def search(
        self,
        path: str,
        road_name: str,
    ):
        """
        Return every geometry matching a road name.
        """

        roads = self.load(path)

        return find_geometry_by_name(
            roads,
            road_name,
        )



    def find_nearest(
        self,
        path: str,
        latitude: float,
        longitude: float,
    ):
        """
        Find nearest road segment using meter distances.
        """

        roads = self.load(path)

        roads = roads[
            roads["name"].notna()
        ].copy()

        if roads.empty:
            return None


        roads = roads.reset_index(drop=True)


        projected = roads.to_crs(
            epsg=3857
        )


        target = gpd.GeoSeries(
            [
                gpd.points_from_xy(
                    [longitude],
                    [latitude],
                )[0]
            ],
            crs="EPSG:4326",
        ).to_crs(
            epsg=3857
        ).iloc[0]


        distances = projected.geometry.distance(
            target
        )


        idx = distances.idxmin()

        nearest = roads.iloc[idx]


        print("\nNearest road check")
        print("------------------")
        print("Input:", latitude, longitude)
        print("Matched:", nearest["name"])
        print(
            "Distance meters:",
            round(
                distances.iloc[idx],
                2
            ),
        )


        return nearest



    def find_nearest_geometry(
        self,
        path: str,
        latitude: float,
        longitude: float,
    ):
        """
        Alias for nearest geometry lookup.
        """

        return self.find_nearest(
            path,
            latitude,
            longitude,
        )



    def find_entire_road(
        self,
        path: str,
        latitude: float,
        longitude: float,
    ):
        """
        Find nearby connected segments sharing the same road name.
        """

        roads = self.load(path)


        roads = roads[
            roads["name"].notna()
        ].copy()


        roads = roads.reset_index(
            drop=True
        )


        projected = roads.to_crs(
            epsg=3857
        )


        target = gpd.GeoSeries(
            [
                gpd.points_from_xy(
                    [longitude],
                    [latitude],
                )[0]
            ],
            crs="EPSG:4326",
        ).to_crs(
            epsg=3857
        ).iloc[0]


        distances = projected.geometry.distance(
            target
        )


        nearest_index = distances.idxmin()


        nearest = roads.iloc[
            nearest_index
        ]


        road_name = nearest["name"]


        print(
            "Nearest road:",
            road_name
        )


        matches = roads[
            roads["name"] == road_name
        ].copy()


        matches = matches.reset_index(
            drop=True
        )


        matches_projected = matches.to_crs(
            epsg=3857
        )


        anchor = (
            projected
            .geometry
            .iloc[nearest_index]
            .centroid
        )


        match_distances = (
            matches_projected
            .geometry
            .centroid
            .distance(anchor)
        )


        matches = matches[
            match_distances < 1000
        ]


        print(
            "Nearby segments:",
            len(matches)
        )


        return matches



    def find_by_name(
        self,
        path: str,
        road_name: str,
    ):
        """
        Find the first geometry matching a road name.
        """

        roads = self.load(path)


        matches = roads[
            roads["name"]
            .fillna("")
            .str.lower()
            ==
            road_name.lower()
        ]


        if matches.empty:
            return None


        return matches.iloc[0]



    def find_nearest_by_name(
        self,
        path: str,
        road_name: str,
        latitude: float,
        longitude: float,
    ):
        """
        Find nearest geometry with a specific road name.
        """

        roads = self.load(path)


        matches = roads[
            roads["name"]
            .fillna("")
            .str.lower()
            ==
            road_name.lower()
        ]


        if matches.empty:
            return None


        matches = matches.reset_index(
            drop=True
        )


        projected = matches.to_crs(
            epsg=3857
        )


        target = gpd.GeoSeries(
            [
                gpd.points_from_xy(
                    [longitude],
                    [latitude],
                )[0]
            ],
            crs="EPSG:4326",
        ).to_crs(
            epsg=3857
        ).iloc[0]


        distances = projected.geometry.distance(
            target
        )


        idx = distances.idxmin()


        return matches.iloc[idx]