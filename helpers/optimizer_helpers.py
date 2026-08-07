import pandas as pd


def optimize_budget(
    roads,
    budget,
    goal="Reduce Highest Risk",
    strategy="AI Recommendation",
):

    roads = roads.copy()

    roads["Cost Efficiency"] = (
        roads["Risk Score"] / roads["Estimated Cost"]
    )

    # -------------------------
    # Apply Strategy
    # -------------------------

    if strategy == "Highest Risk":

        roads = roads.sort_values(
            "Risk Score",
            ascending=False,
        )

    elif strategy == "Lowest Cost":

        roads = roads.sort_values(
            "Estimated Cost",
            ascending=True,
        )

    else:

        roads = roads.sort_values(
            ["Risk Score", "Estimated Cost"],
            ascending=[False, True],
        )

    # -------------------------
    # Apply Optimization Goal
    # -------------------------

    if goal == "Treat Most Roads":

        roads = roads.sort_values(
            "Estimated Cost",
            ascending=True,
        )

    elif goal == "Maximize Lane Miles":

        roads = roads.sort_values(
            "Lane Miles",
            ascending=False,
        )

    # -------------------------
    # Select Roads
    # -------------------------

    selected = []
    spent = 0

    for _, road in roads.iterrows():

        cost = float(road["Estimated Cost"])

        if spent + cost <= budget:

            selected.append(road)

            spent += cost

    selected_df = pd.DataFrame(selected)

    # Force Road IDs to strings
    if not selected_df.empty:

        selected_ids = (
            selected_df["Road ID"]
            .astype(str)
            .str.strip()
            .tolist()
        )

    else:

        selected_ids = []

    return {
        "roads": selected_df,
        "selected_ids": selected_ids,
        "spent": spent,
        "remaining": budget - spent,
        "network_risk": (
            selected_df["Risk Score"].mean()
            if not selected_df.empty
            else 0
        ),
    }