"""Backward-compatible Jackson assumptions component entry point."""

from components.municipality_assumptions import render_municipality_assumptions


def render_jackson_assumptions() -> None:
    """Render the original active-municipality assumptions section."""

    from pilot.municipality_registry import ACTIVE_MUNICIPALITY

    render_municipality_assumptions(ACTIVE_MUNICIPALITY)
