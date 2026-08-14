"""Backward-compatible Jackson scenario component entry points."""

from components.municipality_scenarios import (
    render_municipality_scenario_impact,
    render_municipality_scenario_selector,
)
from pilot.jackson_scenarios import JACKSON_SCENARIOS


def render_jackson_scenario_selector() -> str:
    """Render the original Jackson scenario selector and widget key."""

    return render_municipality_scenario_selector(
        JACKSON_SCENARIOS,
        session_key="jackson_scenario",
    )


def render_jackson_scenario_impact(results: dict) -> None:
    """Render the original scenario impact interface."""

    render_municipality_scenario_impact(results)
