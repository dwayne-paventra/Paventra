"""Backward-compatible Jackson aliases for municipality scenarios."""

from __future__ import annotations

import pandas as pd

from pilot.municipality_scenarios import (
    MUNICIPALITY_SCENARIOS,
    build_municipality_scenario_results,
    get_municipality_scenario,
)


JACKSON_SCENARIOS = MUNICIPALITY_SCENARIOS


def get_jackson_scenario(name: str) -> dict:
    """Return a defensive copy of one configured demonstration scenario."""

    return get_municipality_scenario(name)


def build_jackson_scenario_results(roads: pd.DataFrame, scenario_name: str) -> dict:
    """Run one preset through the existing optimizer and describe its impact.

    The impact is a transparent planning estimate: selected projects are assumed
    to remove their current risk-score points from the portfolio. It is not an
    engineering forecast.
    """

    return build_municipality_scenario_results(roads, scenario_name)
