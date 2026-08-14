"""Backward-compatible Jackson map component entry point."""

from components.municipality_map import render_municipality_map


def render_jackson_map(roads, results: dict) -> None:
    """Render the original map with its legacy widget key."""

    from pilot.municipality_registry import ACTIVE_MUNICIPALITY

    render_municipality_map(
        ACTIVE_MUNICIPALITY,
        roads,
        results,
        selection_key="jackson_road_selection",
    )
