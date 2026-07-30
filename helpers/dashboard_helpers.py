import pandas as pd


def calculate_dashboard_metrics(roads: pd.DataFrame):

    roads_total = len(roads)

    if roads_total == 0:
        return {
            "roads_total": 0,
            "avg_risk": 0,
            "high_risk": 0,
            "medium_risk": 0,
            "low_risk": 0,
            "average_pci": 0,
            "network_health": 0,
            "health_status": "No Data",
            "health_color": "gray",
        }

    avg_risk = round(roads["Risk Score"].mean(), 1)

    high_risk = len(
        roads[roads["Risk Level"] == "High"]
    )

    medium_risk = len(
        roads[roads["Risk Level"] == "Medium"]
    )

    low_risk = len(
        roads[roads["Risk Level"] == "Low"]
    )

    # -----------------------------
    # Create PCI if it doesn't exist
    # -----------------------------

    if "PCI" in roads.columns:

        average_pci = round(
            roads["PCI"].mean(),
            1
        )

    else:

        average_pci = round(
            (100 - roads["Risk Score"]).clip(0, 100).mean(),
            1
        )

    # -----------------------------
    # Executive Network Health
    # -----------------------------

    network_health = round(

        average_pci * 0.70 +

        (1 - high_risk / roads_total) * 30,

        1

    )

    network_health = max(
        0,
        min(
            100,
            network_health
        )
    )

    if network_health >= 85:

        health_status = "Excellent"
        health_color = "#2E7D32"

    elif network_health >= 70:

        health_status = "Good"
        health_color = "#43A047"

    elif network_health >= 55:

        health_status = "Fair"
        health_color = "#F9A825"

    else:

        health_status = "Needs Attention"
        health_color = "#D32F2F"

    return {

        "roads_total": roads_total,

        "avg_risk": avg_risk,

        "high_risk": high_risk,

        "medium_risk": medium_risk,

        "low_risk": low_risk,

        "average_pci": average_pci,

        "network_health": network_health,

        "health_status": health_status,

        "health_color": health_color,

    }