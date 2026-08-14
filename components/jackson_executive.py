"""Backward-compatible Jackson executive component entry point."""

from components.municipality_executive import render_municipality_executive_overview


def render_jackson_executive_overview(roads, results: dict | None = None) -> None:
    """Render the original active-municipality executive overview."""

    from pilot.municipality_registry import ACTIVE_MUNICIPALITY

    render_municipality_executive_overview(ACTIVE_MUNICIPALITY, roads, results)
