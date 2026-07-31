import pandas as pd


def optimize_budget(roads: pd.DataFrame, budget: float):

    roads = roads.copy()

    roads["Cost Efficiency"] = (
        roads["Risk Score"] / roads["Estimated Cost"]
    )

    roads = roads.sort_values(
        "Cost Efficiency",
        ascending=False
    )

    selected = []
    spent = 0

    for _, road in roads.iterrows():

        cost = road["Estimated Cost"]

        if spent + cost <= budget:

            selected.append(road)

            spent += cost

    selected_df = pd.DataFrame(selected)

    return {
        "roads": selected_df,
        "spent": spent,
        "remaining": budget - spent,
        "network_risk": selected_df["Risk Score"].mean()
        if not selected_df.empty else 0
    }