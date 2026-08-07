"""Named, transparent budget scenarios for the Jackson demonstration."""

from __future__ import annotations

import pandas as pd

from helpers.optimizer_helpers import optimize_budget


JACKSON_SCENARIOS = {
    "Preserve the Network": {
        "budget": 1_500_000,
        "goal": "Treat Most Roads",
        "strategy": "Lowest Cost",
        "description": "Prioritizes lower-cost preventive work to extend pavement life.",
    },
    "Balanced Annual Program": {
        "budget": 3_000_000,
        "goal": "Reduce Highest Risk",
        "strategy": "AI Recommendation",
        "description": "Balances near-term risk reduction and stewardship of available funds.",
    },
    "Address Urgent Needs": {
        "budget": 5_000_000,
        "goal": "Reduce Highest Risk",
        "strategy": "Highest Risk",
        "description": "Focuses available funding on the highest-risk segments first.",
    },
}


def get_jackson_scenario(name: str) -> dict:
    """Return a defensive copy of one configured demonstration scenario."""

    if name not in JACKSON_SCENARIOS:
        raise KeyError(f"Unknown Jackson scenario: {name}")
    return dict(JACKSON_SCENARIOS[name])


def build_jackson_scenario_results(roads: pd.DataFrame, scenario_name: str) -> dict:
    """Run one preset through the existing optimizer and describe its impact.

    The impact is a transparent planning estimate: selected projects are assumed
    to remove their current risk-score points from the portfolio. It is not an
    engineering forecast.
    """

    scenario = get_jackson_scenario(scenario_name)
    eligible_roads = roads[roads["Estimated Cost"] > 0].copy()
    results = optimize_budget(
        eligible_roads,
        scenario["budget"],
        scenario["goal"],
        scenario["strategy"],
    )
    selected = results["roads"].copy()
    if not selected.empty:
        selected = selected.sort_values("Risk Score", ascending=False).reset_index(drop=True)
        selected["Priority Rank"] = selected.index + 1
    results["roads"] = selected
    results["selected_ids"] = selected["Road ID"].astype(str).tolist() if not selected.empty else []
    results["scenario"] = scenario
    results["scenario_name"] = scenario_name
    results["selected_lane_miles"] = float(selected["Lane Miles"].sum()) if not selected.empty else 0.0
    results["risk_reduction_points"] = float(selected["Risk Score"].sum()) if not selected.empty else 0.0
    results["network_risk_before"] = float(roads["Risk Score"].mean()) if not roads.empty else 0.0
    residual_total = max(0.0, float(roads["Risk Score"].sum()) - results["risk_reduction_points"])
    results["network_risk_after"] = residual_total / len(roads) if len(roads) else 0.0
    results["risk_reduction_percent"] = (
        ((results["network_risk_before"] - results["network_risk_after"])
         / results["network_risk_before"] * 100)
        if results["network_risk_before"] else 0.0
    )
    return results
