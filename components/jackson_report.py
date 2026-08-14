"""Backward-compatible Jackson report component entry points."""

from components.municipality_report import (
    build_municipality_report,
    municipality_report_filename,
    municipality_report_title,
    render_municipality_report,
)


def build_jackson_report(roads, results: dict) -> bytes:
    """Build the original active-municipality report."""

    from pilot.municipality_registry import ACTIVE_MUNICIPALITY

    return build_municipality_report(ACTIVE_MUNICIPALITY, roads, results)


def render_jackson_report(report_bytes: bytes) -> None:
    """Render the original active-municipality report download."""

    from pilot.municipality_registry import ACTIVE_MUNICIPALITY

    render_municipality_report(ACTIVE_MUNICIPALITY, report_bytes)
