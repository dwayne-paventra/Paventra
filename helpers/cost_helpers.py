import pandas as pd


def calculate_project_budget(risk_level):

    if risk_level == "High":

        materials = 42000
        labor = 21000
        equipment = 15000
        traffic_control = 8500
        engineering = 6000

    elif risk_level == "Medium":

        materials = 26000
        labor = 14000
        equipment = 9000
        traffic_control = 5000
        engineering = 3500

    else:

        materials = 12000
        labor = 7000
        equipment = 3500
        traffic_control = 1800
        engineering = 1500

    subtotal = (
        materials
        + labor
        + equipment
        + traffic_control
        + engineering
    )

    contingency = subtotal * 0.10

    total = subtotal + contingency

    budget_df = pd.DataFrame({

        "Category": [

            "Materials",
            "Labor",
            "Equipment",
            "Traffic Control",
            "Engineering",
            "Contingency"

        ],

        "Cost ($)": [

            materials,
            labor,
            equipment,
            traffic_control,
            engineering,
            contingency

        ]

    })

    return budget_df, total