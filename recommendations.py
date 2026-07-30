def get_recommendations(risk):

    if risk == "High":
        return [
            "Immediate reconstruction",
            "Increase inspection frequency",
            "Allocate emergency funding",
            "Schedule repairs within 6 months"
        ]

    elif risk == "Medium":
        return [
            "Preventive maintenance",
            "Monitor pavement yearly",
            "Resurface in 2-3 years"
        ]

    return [
        "Routine inspections",
        "Preventive sealing",
        "Continue monitoring"
    ]