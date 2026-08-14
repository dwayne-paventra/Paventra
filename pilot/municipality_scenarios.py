"""Municipality-neutral preset scenarios and scenario result generation."""

from __future__ import annotations

from collections.abc import Mapping
import math

import pandas as pd

from helpers.optimizer_helpers import optimize_budget


STANDARD_SCENARIOS = {
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

ROAD_COMMISSION_DEMO_SCENARIOS = {
    "Preserve the Network": {
        "budget": 2_000_000,
        "goal": "Treat Most Roads",
        "strategy": "Lowest Cost",
        "description": "Prioritizes lower-cost preventive work across the maintained network.",
    },
    "Balanced Annual Program": {
        "budget": 3_500_000,
        "goal": "Reduce Highest Risk",
        "strategy": "AI Recommendation",
        "description": "Balances systemwide risk reduction and stewardship of available funds.",
    },
    "Address Urgent Needs": {
        "budget": 5_500_000,
        "goal": "Reduce Highest Risk",
        "strategy": "Highest Risk",
        "description": "Focuses available funding on the highest-risk maintained segments first.",
    },
}

SCENARIO_CATALOGS = {
    "standard": STANDARD_SCENARIOS,
    "road_commission_demo": ROAD_COMMISSION_DEMO_SCENARIOS,
}
DEFAULT_SCENARIO_CATALOG_ID = "standard"

# Phase 4 compatibility alias for callers expecting the original shared catalog.
MUNICIPALITY_SCENARIOS = STANDARD_SCENARIOS


def validate_scenario_catalogs(catalogs: Mapping[str, Mapping]) -> None:
    """Validate scenario catalogs without invoking scenario calculations."""

    if not isinstance(catalogs, Mapping) or not catalogs:
        raise ValueError("Scenario catalogs must be a non-empty mapping.")

    required_fields = ("budget", "goal", "strategy", "description")
    for catalog_id, catalog in catalogs.items():
        if not isinstance(catalog_id, str) or not catalog_id.strip():
            raise ValueError("Scenario catalog ID must be a non-empty string.")
        if not isinstance(catalog, Mapping) or not catalog:
            raise ValueError(
                f"Scenario catalog '{catalog_id}' must contain at least one scenario."
            )

        # Mapping keys are the scenario IDs, so duplicate IDs cannot survive
        # construction. Validate each retained ID and definition explicitly.
        for scenario_name, scenario in catalog.items():
            if not isinstance(scenario_name, str) or not scenario_name.strip():
                raise ValueError(
                    f"Scenario catalog '{catalog_id}' has an empty scenario name."
                )
            if not isinstance(scenario, Mapping):
                raise ValueError(
                    f"Scenario '{scenario_name}' in catalog '{catalog_id}' must be a mapping."
                )
            missing = [field for field in required_fields if field not in scenario]
            if missing:
                raise ValueError(
                    f"Scenario '{scenario_name}' in catalog '{catalog_id}' is missing "
                    f"required fields: {', '.join(missing)}."
                )

            budget = scenario["budget"]
            if (
                isinstance(budget, bool)
                or not isinstance(budget, (int, float))
                or not math.isfinite(budget)
                or budget <= 0
            ):
                raise ValueError(
                    f"Scenario '{scenario_name}' in catalog '{catalog_id}' field "
                    "'budget' must be a positive finite number."
                )
            for field_name in ("goal", "strategy", "description"):
                value = scenario[field_name]
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(
                        f"Scenario '{scenario_name}' in catalog '{catalog_id}' field "
                        f"'{field_name}' must be a non-empty string."
                    )


validate_scenario_catalogs(SCENARIO_CATALOGS)


def get_scenario_catalog(catalog_id: str) -> dict[str, dict]:
    """Return a defensive copy of one configured scenario catalog."""

    try:
        catalog = SCENARIO_CATALOGS[catalog_id]
    except KeyError as exc:
        available = ", ".join(sorted(SCENARIO_CATALOGS))
        raise ValueError(
            f"Unknown scenario catalog '{catalog_id}'. Available catalogs: {available}."
        ) from exc
    return {name: dict(scenario) for name, scenario in catalog.items()}


def get_municipality_scenario(
    name: str,
    catalog_id: str = DEFAULT_SCENARIO_CATALOG_ID,
) -> dict:
    """Return a defensive copy of one configured demonstration scenario."""

    catalog = get_scenario_catalog(catalog_id)
    if name not in catalog:
        raise KeyError(f"Unknown scenario '{name}' in catalog '{catalog_id}'")
    return dict(catalog[name])


def build_municipality_scenario_results(
    roads: pd.DataFrame,
    scenario_name: str,
    catalog_id: str = DEFAULT_SCENARIO_CATALOG_ID,
) -> dict:
    """Run one preset through the existing optimizer and describe its impact.

    The impact is a transparent planning estimate: selected projects are assumed
    to remove their current risk-score points from the portfolio. It is not an
    engineering forecast.
    """

    scenario = get_municipality_scenario(scenario_name, catalog_id)
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
