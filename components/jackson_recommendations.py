"""Backward-compatible Jackson recommendations component entry point."""

from components.municipality_recommendations import render_municipality_recommendations


def render_jackson_recommendations(results: dict) -> None:
    """Render the original active-municipality recommendations section."""

    from pilot.municipality_registry import ACTIVE_MUNICIPALITY

    render_municipality_recommendations(ACTIVE_MUNICIPALITY, results)
